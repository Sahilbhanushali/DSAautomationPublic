#!/usr/bin/env python3
"""
Compile and run a problem's solution, and record the attempt.

Usage:

    python3 tools/run.py                       # problem in the current folder
    python3 tools/run.py two-sum
    python3 tools/run.py problems/arrays/two-sum
    python3 tools/run.py problems/arrays/two-sum/solution.cpp

Options:

    --no-record     run without touching problem.json
    --              everything after this is passed to the program

If the problem folder contains input.txt it is fed to the program on
stdin; otherwise the program reads from your terminal as usual.

Build artifacts go to a temporary directory, so nothing is left behind
in the problem folder and the solution source is never modified.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time

import common


# ==================================================
# Language configuration
# ==================================================
#
# compile(source, build_dir) -> command list, or None when not needed
# execute(source, build_dir) -> command list

def cpp_compile(source, build_dir):
    return [
        "g++",
        "-std=c++17",
        "-O2",
        "-o", str(build_dir / "solution"),
        str(source),
    ]


def cpp_execute(source, build_dir):
    return [str(build_dir / "solution")]


def python_compile(source, build_dir):
    return None


def python_execute(source, build_dir):
    return [sys.executable, str(source)]


def java_compile(source, build_dir):
    return ["javac", "-d", str(build_dir), str(source)]


def java_execute(source, build_dir):
    return ["java", "-cp", str(build_dir), source.stem]


RUNNERS = {
    ".cpp": {
        "name": "C++",
        "tool": "g++",
        "compile": cpp_compile,
        "execute": cpp_execute,
    },
    ".py": {
        "name": "Python",
        "tool": None,
        "compile": python_compile,
        "execute": python_execute,
    },
    ".java": {
        "name": "Java",
        "tool": "javac",
        "compile": java_compile,
        "execute": java_execute,
    },
}


# ==================================================
# Execution
# ==================================================

def check_toolchain(runner):
    """Fail early and clearly when the compiler isn't installed."""

    tool = runner["tool"]

    if tool and shutil.which(tool) is None:
        raise common.ToolError(
            f"'{tool}' was not found in your PATH.\n"
            f"   Install it to run {runner['name']} solutions."
        )


def compile_solution(runner, source, build_dir):
    """
    Build the solution.

    Returns True on success. Compiler diagnostics are printed as-is.
    """

    command = runner["compile"](source, build_dir)

    if command is None:
        return True

    print(f"🔨 Compiling {source.name} ...", flush=True)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

    except OSError as error:
        raise common.ToolError(f"Could not run the compiler: {error}") from error

    output = (result.stdout + result.stderr).strip()

    if output:
        print()
        print(output)
        print()

    if result.returncode != 0:
        print("❌ Compilation failed.")
        return False

    return True


def execute_solution(runner, source, build_dir, program_args):
    """
    Run the built program.

    Returns (exit_code, elapsed_seconds). stdin comes from input.txt when
    that file exists, otherwise from the terminal.
    """

    command = runner["execute"](source, build_dir) + list(program_args)

    input_file = source.parent / common.INPUT_FILENAME
    stdin_handle = None

    if input_file.exists():
        print(f"📥 stdin: {common.INPUT_FILENAME}")
        stdin_handle = input_file.open("rb")

    print(f"▶️  Running {source.name} ...")
    print("-" * 50, flush=True)

    started = time.perf_counter()

    try:
        result = subprocess.run(
            command,
            stdin=stdin_handle,
            check=False,
        )
        exit_code = result.returncode

    except OSError as error:
        raise common.ToolError(f"Could not start the program: {error}") from error

    finally:
        if stdin_handle is not None:
            stdin_handle.close()

    elapsed = time.perf_counter() - started

    print("-" * 50)

    return exit_code, elapsed


def describe_exit(exit_code):
    """Explain an exit code, including the usual signal deaths."""

    if exit_code == 0:
        return "✅ Finished (exit code 0)"

    if exit_code < 0:
        return (
            f"❌ Killed by signal {-exit_code} "
            "(segfault, timeout or out of memory)"
        )

    return f"❌ Failed (exit code {exit_code})"


# ==================================================
# Main
# ==================================================

def parse_arguments(argv):
    """Split argv into (target, record, program_args)."""

    record = True
    target = None
    program_args = []

    rest = list(argv)

    if "--" in rest:
        index = rest.index("--")
        program_args = rest[index + 1:]
        rest = rest[:index]

    for argument in rest:
        if argument in ("--no-record", "-n"):
            record = False

        elif argument.startswith("-"):
            raise common.ToolError(f"Unknown option: {argument}")

        elif target is None:
            target = argument

        else:
            raise common.ToolError(
                "Only one problem can be run at a time.\n"
                "   Pass program arguments after '--'."
            )

    return target, record, program_args


def main():
    target, record, program_args = parse_arguments(sys.argv[1:])

    problem_dir = common.resolve_problem(target or os.getcwd())

    solution_file = common.find_solution_file(problem_dir)

    if solution_file is None:
        raise common.ToolError(
            f"No solution file in {common.relative_to_root(problem_dir)}"
        )

    runner = RUNNERS.get(solution_file.suffix)

    if runner is None:
        raise common.ToolError(
            f"Don't know how to run {solution_file.suffix} files."
        )

    check_toolchain(runner)

    print()
    print(f"📂 {common.relative_to_root(problem_dir)}")

    with tempfile.TemporaryDirectory(prefix="dsa-build-") as build_root:
        build_dir = Path(build_root)

        if not compile_solution(runner, solution_file, build_dir):
            finish(problem_dir, passed=False, record=record)
            sys.exit(1)

        exit_code, elapsed = execute_solution(
            runner,
            solution_file,
            build_dir,
            program_args,
        )

    print(describe_exit(exit_code))
    print(f"⏱️  {elapsed:.3f}s")

    finish(problem_dir, passed=exit_code == 0, record=record)

    sys.exit(0 if exit_code == 0 else 1)


def finish(problem_dir, passed, record):
    """
    Record the attempt and refresh the index.

    A successful local run is an attempt and nothing more: whether the
    problem is solved is decided by the online judge, not by g++.
    """

    if not record:
        return

    if not (problem_dir / common.METADATA_FILENAME).exists():
        print(
            "\n⚠️ No problem.json here, so the attempt wasn't recorded.\n"
            "   Run: python3 tools/migrate.py"
        )
        return

    result = common.record_run(problem_dir, passed)

    print()
    print(f"📊 Attempts: {result['attempts']}")

    if result["promoted"]:
        print(f"   Status: {common.display_status(result['status'])}")

    import sync_index

    sync_index.sync_index()


if __name__ == "__main__":
    common.run_cli(main)
