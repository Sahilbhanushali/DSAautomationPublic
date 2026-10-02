#!/usr/bin/env python3
"""
Sync a problem's README.md from the header comment in its solution file.

Reads the "Problem:" text and every "Approach N: <name>" block
(Idea / Time / Space) from the solution file, and writes them into
the marked sections of README.md.

Saving a solution that contains real code also moves the problem from
Not Started to In Progress. Nothing else about the status is touched:
a solved problem stays solved.

Also updates the global PROBLEMS.md index after syncing.

Usage:
    python3 tools/sync_readme.py
    python3 tools/sync_readme.py <problem-folder>
    python3 tools/sync_readme.py <solution-file>
"""

from pathlib import Path
import re
import sys
import textwrap

import common
import sync_index


# ==================================================
# Configuration
# ==================================================

ROOT = common.ROOT
PROBLEMS_DIR = common.PROBLEMS_DIR

SOLUTION_EXTENSIONS = common.SOLUTION_EXTENSIONS

PROBLEM_START = common.PROBLEM_START
PROBLEM_END = common.PROBLEM_END

APPROACHES_START = common.APPROACHES_START
APPROACHES_END = common.APPROACHES_END

DELIMITER_RE = common.DELIMITER_RE

find_solution_file = common.find_solution_file

APPROACH_RE = re.compile(
    r"^\s*Approach\s+(\d+)\s*:\s*(.*?)\s*$",
    re.IGNORECASE,
)

FIELD_RE = re.compile(
    r"^\s*(Idea|Time|Space)\s*:\s*(.*)$",
    re.IGNORECASE,
)

PROBLEM_RE = re.compile(
    r"^\s*Problem\s*:\s*(.*)$",
    re.IGNORECASE,
)


# ==================================================
# Parsing the solution file
# ==================================================

def clean_block(lines):
    """
    Dedent a list of lines and trim blank lines at both ends.
    """

    return textwrap.dedent("\n".join(lines)).strip()


def extract_header_body(text):
    """
    Return the lines between the 2nd and 3rd
    "=====" delimiter lines.
    """

    lines = text.splitlines()

    delimiters = [
        index
        for index, line in enumerate(lines)
        if DELIMITER_RE.match(line)
    ]

    if len(delimiters) < 3:
        return None

    return lines[delimiters[1] + 1 : delimiters[2]]


def parse_solution(text):
    """
    Parse the header comment of a solution file.

    Returns:

        {
            "problem": str,
            "approaches": [
                {
                    "number": int,
                    "name": str,
                    "idea": str,
                    "time": str,
                    "space": str
                }
            ]
        }

    Returns None if the header can't be found.
    """

    body = extract_header_body(text)

    if body is None:
        return None

    problem_lines = []
    approaches = []

    current = None
    field = None

    for line in body:

        # ------------------------------------------
        # Approach detection
        # ------------------------------------------

        approach_match = APPROACH_RE.match(line)

        if approach_match:

            current = {
                "number": int(approach_match.group(1)),
                "name": (
                    approach_match.group(2)
                    or f"Approach {approach_match.group(1)}"
                ),
                "idea": [],
                "time": [],
                "space": [],
            }

            approaches.append(current)

            field = None

            continue

        # ------------------------------------------
        # Problem statement
        # ------------------------------------------

        if current is None:

            problem_match = PROBLEM_RE.match(line)

            if problem_match:

                field = "problem"

                if problem_match.group(1).strip():
                    problem_lines.append(problem_match.group(1))

                continue

            if field == "problem":
                problem_lines.append(line)

            continue

        # ------------------------------------------
        # Approach fields
        # ------------------------------------------

        field_match = FIELD_RE.match(line)

        if field_match:

            field = field_match.group(1).lower()

            rest = field_match.group(2)

            if rest.strip():
                current[field].append(rest)

            continue

        if field is not None:
            current[field].append(line)

    # ----------------------------------------------
    # Clean parsed values
    # ----------------------------------------------

    for approach in approaches:

        approach["idea"] = clean_block(approach["idea"])

        approach["time"] = " ".join(clean_block(approach["time"]).split())

        approach["space"] = " ".join(clean_block(approach["space"]).split())

    return {
        "problem": clean_block(problem_lines),
        "approaches": approaches,
    }


# ==================================================
# Rendering README sections
# ==================================================

def render_problem(problem):
    """
    Render the Problem section body.
    """

    if not problem:
        return "> Write the problem statement here."

    return problem


def render_approaches(approaches):
    """
    Render the Approaches comparison table and the detail blocks.
    """

    if not approaches:
        return "_No approaches defined in the solution file._"

    parts = [
        "| # | Approach | Time | Space |",
        "|---|---|---|---|",
    ]

    # ----------------------------------------------
    # Comparison table
    # ----------------------------------------------

    for approach in approaches:

        parts.append(
            f"| {approach['number']} "
            f"| {common.table_cell(approach['name'])} "
            f"| {common.table_cell(approach['time'])} "
            f"| {common.table_cell(approach['space'])} |"
        )

    # ----------------------------------------------
    # Detailed approaches
    # ----------------------------------------------

    for approach in approaches:

        time = f"`{approach['time']}`" if approach["time"] else "—"
        space = f"`{approach['space']}`" if approach["space"] else "—"

        parts.append("")

        parts.append(
            f"### Approach {approach['number']}: {approach['name']}"
        )

        parts.append("")

        parts.append(approach["idea"] or "_Not written yet._")

        parts.append("")

        parts.append(f"**Time:** {time} · **Space:** {space}")

    return "\n".join(parts)


# ==================================================
# Syncing one problem
# ==================================================

def sync_problem(problem_dir, quiet=False, update_index=True, record=True):
    """
    Sync one problem folder.

    Rewrites only the marked README sections, records the save in
    problem.json, and refreshes the global index.

    Pass record=False for syncs that aren't a user save (migration,
    bulk repairs) so no activity date is invented.

    Returns "updated", "unchanged" or "skipped".
    """

    problem_dir = Path(problem_dir)

    readme_file = problem_dir / common.README_FILENAME

    solution_file = find_solution_file(problem_dir)

    def skip(reason):

        if not quiet:
            print(f"⏭️  {problem_dir.name}: {reason}")

        return "skipped"

    if not readme_file.exists():
        return skip("no README.md")

    if solution_file is None:
        return skip("no solution file")

    try:
        parsed = parse_solution(
            solution_file.read_text(encoding="utf-8")
        )

        readme = readme_file.read_text(encoding="utf-8")

    except OSError as error:
        return skip(f"could not read files ({error})")

    if parsed is None:
        return skip(
            f"couldn't find the header block in {solution_file.name}"
        )

    # ----------------------------------------------
    # Rewrite the marked sections only
    # ----------------------------------------------

    new_readme = common.replace_between(
        readme,
        PROBLEM_START,
        PROBLEM_END,
        render_problem(parsed["problem"]),
    )

    if new_readme is None:
        return skip("README has no problem sync markers")

    new_readme = common.replace_between(
        new_readme,
        APPROACHES_START,
        APPROACHES_END,
        render_approaches(parsed["approaches"]),
    )

    if new_readme is None:
        return skip("README has no approaches sync markers")

    changed = common.write_if_changed(readme_file, new_readme)

    # ----------------------------------------------
    # Bookkeeping
    # ----------------------------------------------

    started = record_activity(problem_dir, quiet) if record else False

    if update_index:
        sync_index.sync_index(quiet=True)

    if not quiet:

        if changed:
            print(f"✅ {problem_dir.name}: README updated")
        else:
            print(f"✔️  {problem_dir.name}: already up to date")

    return "updated" if (changed or started) else "unchanged"


def record_activity(problem_dir, quiet):
    """
    Update problem.json after a save. Never fatal: a metadata problem
    must not stop the README from syncing.
    """

    try:
        event = common.record_save(problem_dir)

    except common.ToolError as error:
        if not quiet:
            print(f"⚠️ {error}")
        return False

    if event == "started" and not quiet:
        print("   Status: Not Started → In Progress")

    return event is not None


# ==================================================
# Sync all problems
# ==================================================

def sync_all():
    """
    Sync every problem, then refresh the index once.
    """

    if not PROBLEMS_DIR.exists():
        print(f"No problems folder found at {PROBLEMS_DIR}")
        return

    problem_dirs = common.iter_problem_dirs()

    if not problem_dirs:
        print("No problems found.")
        return

    counts = {"updated": 0, "unchanged": 0, "skipped": 0}

    for problem_dir in problem_dirs:

        result = sync_problem(problem_dir, update_index=False)

        counts[result] += 1

    sync_index.sync_index(quiet=True)

    print(
        f"\nDone: "
        f"{counts['updated']} updated, "
        f"{counts['unchanged']} unchanged, "
        f"{counts['skipped']} skipped."
    )


# ==================================================
# Main
# ==================================================

def main():

    if len(sys.argv) < 2:
        sync_all()
        return

    sync_problem(common.resolve_problem(sys.argv[1]))


if __name__ == "__main__":
    common.run_cli(main)
