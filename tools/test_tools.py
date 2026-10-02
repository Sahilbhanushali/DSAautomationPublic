#!/usr/bin/env python3
"""
Self-check for the DSA tooling.

Covers the parts that would silently produce wrong data if they broke:
scaffold detection, status transitions, marker handling and migration.

Run:

    python3 tools/test_tools.py
"""

import tempfile
from pathlib import Path

import common
import migrate
import new_problem
import sync_readme


EMPTY_CPP = new_problem.CPP_TEMPLATE.format(
    header=new_problem.build_header(
        "Two Sum", "Arrays", "Easy", "LeetCode", ["Brute Force", "Optimal"]
    ),
    methods=new_problem.cpp_methods(["Brute Force", "Optimal"]),
    class_name="TwoSum",
)

EMPTY_PY = new_problem.PYTHON_TEMPLATE.format(
    header=new_problem.build_header(
        "Two Sum", "Arrays", "Easy", "LeetCode", ["Optimal"]
    ),
    methods=new_problem.python_methods(["Optimal"]),
    class_name="TwoSum",
)

EMPTY_JAVA = new_problem.JAVA_TEMPLATE.format(
    header=new_problem.build_header(
        "Two Sum", "Arrays", "Easy", "LeetCode", ["Optimal"]
    ),
    methods=new_problem.java_methods(["Optimal"]),
    class_name="TwoSum",
)


def write(directory, name, text):
    path = Path(directory) / name
    path.write_text(text, encoding="utf-8")
    return path


def test_scaffold_is_not_meaningful():
    """A freshly generated file must never look like work in progress."""

    with tempfile.TemporaryDirectory() as directory:

        for name, text in (
            ("solution.cpp", EMPTY_CPP),
            ("solution.py", EMPTY_PY),
            ("Solution.java", EMPTY_JAVA),
        ):
            assert not common.has_meaningful_code(write(directory, name, text)), name

        # Reformatted braces and extra comments are still not code.
        reformatted = EMPTY_CPP.replace("{\n", "\n{\n") + "\n// todo: think\n"

        assert not common.has_meaningful_code(
            write(directory, "reformatted.cpp", reformatted)
        )


def test_real_code_is_meaningful():
    """One real statement is enough to count as work."""

    with tempfile.TemporaryDirectory() as directory:

        cpp = EMPTY_CPP.replace(
            "    void bruteForce() {\n",
            "    void bruteForce() {\n        int n;\n        cin >> n;\n",
        )
        assert common.has_meaningful_code(write(directory, "a.cpp", cpp))

        python = EMPTY_PY.replace("        pass", "        return sorted(self.x)")
        assert common.has_meaningful_code(write(directory, "b.py", python))

        java = EMPTY_JAVA.replace(
            "    static void optimal() {\n",
            "    static void optimal() {\n        int total = 0;\n",
        )
        assert common.has_meaningful_code(write(directory, "C.java", java))


def test_status_transitions_are_conservative():
    """Saving promotes only not_started, and never moves anything back."""

    with tempfile.TemporaryDirectory() as directory:

        problem_dir = Path(directory)
        metadata_file = problem_dir / common.METADATA_FILENAME

        write(problem_dir, "solution.cpp", EMPTY_CPP)

        metadata = common.new_metadata(
            "Two Sum", "Arrays", "Easy", "C++", "LeetCode", None, ["Optimal"]
        )
        common.save_metadata(metadata_file, metadata)

        # Empty scaffold: nothing happens.
        assert common.record_save(problem_dir) is None
        assert common.load_metadata(metadata_file)["status"] == common.NOT_STARTED

        # Real code: not_started -> in_progress.
        write(
            problem_dir,
            "solution.cpp",
            EMPTY_CPP.replace(
                "    void bruteForce() {\n",
                "    void bruteForce() {\n        int n = 1;\n",
            ),
        )

        assert common.record_save(problem_dir) == "started"
        assert common.load_metadata(metadata_file)["status"] == common.IN_PROGRESS

        # Solved stays solved, no matter how often it is saved.
        for status in (common.SOLVED, common.REVISIT):

            metadata = common.load_metadata(metadata_file)
            metadata["status"] = status
            common.save_metadata(metadata_file, metadata)

            common.record_save(problem_dir)

            assert common.load_metadata(metadata_file)["status"] == status

        # Saving never invents attempts.
        assert common.load_metadata(metadata_file)["attempts"] == 0


def test_run_records_attempt_but_never_solves():
    """A passing local run is an attempt, not an acceptance."""

    with tempfile.TemporaryDirectory() as directory:

        problem_dir = Path(directory)
        metadata_file = problem_dir / common.METADATA_FILENAME

        common.save_metadata(
            metadata_file,
            common.new_metadata(
                "Two Sum", "Arrays", "Easy", "C++", "LeetCode", None, ["Optimal"]
            ),
        )

        result = common.record_run(problem_dir, passed=True)

        metadata = common.load_metadata(metadata_file)

        assert result["attempts"] == 1
        assert metadata["status"] == common.IN_PROGRESS
        assert metadata["last_test_result"] == "passed"
        assert metadata["date_solved"] is None

        common.record_run(problem_dir, passed=False)

        metadata = common.load_metadata(metadata_file)

        assert metadata["attempts"] == 2
        assert metadata["last_test_result"] == "failed"


def test_sync_is_idempotent_and_marker_bound():
    """Syncing twice changes nothing, and user text outside markers survives."""

    with tempfile.TemporaryDirectory() as directory:

        problem_dir = Path(directory)

        write(problem_dir, "solution.cpp", EMPTY_CPP)

        readme = new_problem.README_TEMPLATE.format(
            problem="Two Sum",
            category="Arrays",
            difficulty="Easy",
            language="C++",
            source="LeetCode",
            url="-",
        ) + "\nMY OWN NOTES\n"

        readme_file = write(problem_dir, "README.md", readme)

        sync_readme.sync_problem(problem_dir, quiet=True, update_index=False)
        first = readme_file.read_text(encoding="utf-8")

        sync_readme.sync_problem(problem_dir, quiet=True, update_index=False)

        assert readme_file.read_text(encoding="utf-8") == first
        assert "MY OWN NOTES" in first
        assert "| 1 | Brute Force |" in first


def test_write_if_changed():
    """Unchanged content must not touch the file."""

    with tempfile.TemporaryDirectory() as directory:

        path = Path(directory) / "x.txt"

        assert common.write_if_changed(path, "hello") is True
        assert common.write_if_changed(path, "hello") is False
        assert common.write_if_changed(path, "bye") is True


def test_migration_recovers_and_reports():
    """Legacy folders gain metadata; unknown fields are reported, not invented."""

    with tempfile.TemporaryDirectory() as directory:

        problem_dir = Path(directory)

        # An old-style header: no Source, no numbered approaches.
        write(
            problem_dir,
            "trapping-rain-water.cpp",
            "/*\n" + "=" * 50 + "\n"
            "Problem: trapping rain water\n"
            "Category: Arrays\n"
            "Difficulty: Medium\n"
            + "=" * 50 + "\n\nProblem:\n\nApproach:\n\n"
            + "=" * 50 + "\n*/\n\nint main() {\n    return 0;\n}\n",
        )

        notes = migrate.migrate_problem(problem_dir, dry_run=False)

        metadata = common.load_metadata(problem_dir / common.METADATA_FILENAME)

        assert metadata["problem"] == "trapping rain water"
        assert metadata["category"] == "Arrays"
        assert metadata["difficulty"] == "Medium"
        assert metadata["language"] == "C++"
        assert metadata["source"] == ""
        assert metadata["status"] == common.NOT_STARTED
        assert any("source" in note for note in notes)

        readme = (problem_dir / "README.md").read_text(encoding="utf-8")

        assert common.PROBLEM_START in readme
        assert common.APPROACHES_START in readme

        # Running it again is a no-op.
        assert migrate.migrate_problem(problem_dir, dry_run=False) == []


def test_migration_keeps_user_text():
    """A marker-less README never loses what the user wrote."""

    with tempfile.TemporaryDirectory() as directory:

        problem_dir = Path(directory)

        write(problem_dir, "solution.cpp", EMPTY_CPP)

        write(
            problem_dir,
            "README.md",
            "# suar\n\n## Problem\n\nMY OWN PROBLEM STATEMENT\n\n---\n"
            "\n## Approaches\n\n> Write the problem statement here.\n",
        )

        migrate.migrate_problem(problem_dir, dry_run=False)

        readme = (problem_dir / "README.md").read_text(encoding="utf-8")

        assert "MY OWN PROBLEM STATEMENT" in readme
        assert common.PROBLEM_START in readme
        assert common.APPROACHES_START in readme


def main():

    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]

    for test in tests:
        test()
        print(f"✓ {test.__name__}")

    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
