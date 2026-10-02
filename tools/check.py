#!/usr/bin/env python3
"""
Validate the repository: metadata, documentation and the global index.

Usage:

    python3 tools/check.py
    python3 tools/check.py <problem>

Exits with a non-zero status when anything is wrong, so it can be used
as a pre-commit or CI gate.
"""

import sys

import common
import sync_index


# ==================================================
# Per-problem checks
# ==================================================

REQUIRED_FIELDS = (
    "problem",
    "category",
    "difficulty",
    "language",
    "source",
)


def check_metadata(problem_dir, issues):
    """Validate problem.json."""

    metadata_file = problem_dir / common.METADATA_FILENAME

    if not metadata_file.exists():
        issues.append(
            f"{common.METADATA_FILENAME} missing "
            "(run: python3 tools/migrate.py)"
        )
        return

    try:
        metadata = common.load_metadata(metadata_file)

    except common.ToolError as error:
        issues.append(str(error))
        return

    for field in REQUIRED_FIELDS:
        if not common.clean_value(metadata.get(field)):
            issues.append(f'{common.METADATA_FILENAME}: missing "{field}"')

    status = common.normalize_status(metadata.get("status"))

    if status not in common.VALID_STATUSES:
        issues.append(
            f'{common.METADATA_FILENAME}: invalid status "{status}" '
            f"(expected one of {', '.join(common.VALID_STATUSES)})"
        )

    for counter in ("attempts", "revisit_count"):

        value = metadata.get(counter, 0)

        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            issues.append(
                f'{common.METADATA_FILENAME}: "{counter}" must be a '
                f"non-negative integer (found {value!r})"
            )

    approaches = metadata.get("approaches", [])

    if not isinstance(approaches, list):
        issues.append(f'{common.METADATA_FILENAME}: "approaches" must be a list')

    if status == common.SOLVED and not metadata.get("date_solved"):
        issues.append(
            f'{common.METADATA_FILENAME}: solved but "date_solved" is empty'
        )


def check_readme(problem_dir, issues):
    """Validate README.md and its sync markers."""

    readme_file = problem_dir / common.README_FILENAME

    if not readme_file.exists():
        issues.append(f"{common.README_FILENAME} missing")
        return

    try:
        readme = readme_file.read_text(encoding="utf-8")

    except OSError as error:
        issues.append(f"Could not read {common.README_FILENAME}: {error}")
        return

    markers = (
        ("PROBLEM", common.PROBLEM_START, common.PROBLEM_END),
        ("APPROACHES", common.APPROACHES_START, common.APPROACHES_END),
    )

    for name, start, end in markers:
        if start not in readme or end not in readme:
            issues.append(
                f"{common.README_FILENAME}: missing {name} sync markers"
            )


def check_solution(problem_dir, issues):
    """Validate that a runnable solution file exists."""

    if common.find_solution_file(problem_dir) is None:
        issues.append(
            "no solution file "
            f"({', '.join(common.SOLUTION_EXTENSIONS)})"
        )


def check_problem(problem_dir):
    """Run every check for one problem. Returns a list of issues."""

    issues = []

    check_metadata(problem_dir, issues)
    check_readme(problem_dir, issues)
    check_solution(problem_dir, issues)

    return issues


# ==================================================
# Repository checks
# ==================================================

def check_index(issues):
    """Validate PROBLEMS.md and whether it is up to date."""

    if not common.INDEX_FILE.exists():
        issues.append("PROBLEMS.md missing (run: python3 tools/sync_index.py)")
        return

    try:
        text = common.INDEX_FILE.read_text(encoding="utf-8")

    except OSError as error:
        issues.append(f"Could not read PROBLEMS.md: {error}")
        return

    if common.INDEX_START not in text or common.INDEX_END not in text:
        issues.append("PROBLEMS.md: missing INDEX markers")
        return

    if not sync_index.sync_index(check_only=True, quiet=True):
        issues.append(
            "PROBLEMS.md is out of date (run: python3 tools/sync_index.py)"
        )


# ==================================================
# Reporting
# ==================================================

def report(problem_dir, issues):
    """Print the result for one problem."""

    label = common.relative_to_root(problem_dir)

    if not issues:
        print(f"✓ {label}")
        return

    print(f"✗ {label}")

    for issue in issues:
        print(f"  {issue}")


# ==================================================
# Main
# ==================================================

def main():

    print()
    print("DSA Repository Check")
    print()

    if len(sys.argv) > 1:
        problem_dirs = [common.resolve_problem(sys.argv[1])]
    else:
        problem_dirs = common.iter_problem_dirs()

    if not problem_dirs:
        print("No problems found.")
        print()
        return

    total_issues = 0

    for problem_dir in problem_dirs:

        issues = check_problem(problem_dir)
        total_issues += len(issues)

        report(problem_dir, issues)

    # The index describes the whole repository, so only check it on a
    # full run -- a single-problem check can't tell whether it is stale.

    if len(sys.argv) == 1:

        index_issues = []
        check_index(index_issues)
        total_issues += len(index_issues)

        print()

        if index_issues:
            print("✗ PROBLEMS.md")
            for issue in index_issues:
                print(f"  {issue}")
        else:
            print("✓ PROBLEMS.md")

    print()

    if total_issues:
        print(
            f"{len(problem_dirs)} problems checked, "
            f"{total_issues} issue{'s' if total_issues != 1 else ''} found."
        )
        print()
        sys.exit(1)

    print(f"{len(problem_dirs)} problems checked. No problems found.")
    print()


if __name__ == "__main__":
    common.run_cli(main)
