#!/usr/bin/env python3

"""
Manage DSA problem status by hand.

This is the manual override, not the normal workflow. Saving a solution
already moves a problem to In Progress and running it already records an
attempt. Use this to correct metadata, mark a problem solved once the
judge accepts it, or recover from a mistake.

Usage:

    python3 tools/status.py start <problem>
    python3 tools/status.py attempt <problem>
    python3 tools/status.py solved <problem>
    python3 tools/status.py revisit <problem>
    python3 tools/status.py reset <problem>
    python3 tools/status.py show <problem>
    python3 tools/status.py list

Examples:

    python3 tools/status.py solved twooo-sum
    python3 tools/status.py show twooo-sum
    python3 tools/status.py list
"""

import sys

import common
import sync_index


display_status = common.display_status


# ==================================================
# Status Operations
# ==================================================

def set_start(metadata):
    """
    Mark a problem as in progress.
    """

    metadata["status"] = common.IN_PROGRESS


def set_attempt(metadata):
    """
    Register an attempt.

    Attempts are incremented and the problem becomes in progress.
    """

    metadata["attempts"] = common.as_count(metadata.get("attempts")) + 1
    metadata["status"] = common.IN_PROGRESS


def set_solved(metadata):
    """
    Mark a problem as solved.

    This is deliberately manual: only you know whether the online judge
    accepted the submission.
    """

    metadata["status"] = common.SOLVED
    metadata["date_solved"] = common.today()


def set_revisit(metadata):
    """
    Mark a problem for revisit.

    Each time the problem is explicitly marked for revisit,
    revisit_count increases by one.
    """

    metadata["revisit_count"] = (
        common.as_count(metadata.get("revisit_count")) + 1
    )

    metadata["status"] = common.REVISIT


def set_reset(metadata):
    """
    Reset the problem to not started.

    Attempts and revisit count are preserved because they are
    historical information.
    """

    metadata["status"] = common.NOT_STARTED
    metadata["date_solved"] = None


ACTIONS = {
    "start": set_start,
    "attempt": set_attempt,
    "solved": set_solved,
    "revisit": set_revisit,
    "reset": set_reset,
}


# ==================================================
# Show Problem
# ==================================================

def show_problem(metadata):
    """
    Display detailed problem information.
    """

    rows = [
        ("Problem", metadata.get("problem")),
        ("Category", metadata.get("category")),
        ("Difficulty", metadata.get("difficulty")),
        ("Language", metadata.get("language")),
        ("Source", metadata.get("source")),
        ("Status", display_status(metadata.get("status"))),
        ("Attempts", common.as_count(metadata.get("attempts"))),
        ("Revisits", common.as_count(metadata.get("revisit_count"))),
        ("Date Added", metadata.get("date_added")),
        ("Date Solved", metadata.get("date_solved")),
        ("Last Activity", metadata.get("last_activity")),
        ("Last Tested", metadata.get("last_tested")),
        ("Test Result", metadata.get("last_test_result")),
    ]

    print()
    print("=" * 50)

    for label, value in rows:
        print(f"{label:<14}: {value if value not in (None, '') else '—'}")

    print("=" * 50)
    print()


# ==================================================
# List Problems
# ==================================================

def list_problems():
    """
    Display all problems in a compact table.
    """

    problems = []

    for problem_dir in common.iter_problem_dirs():

        metadata_file = problem_dir / common.METADATA_FILENAME

        if not metadata_file.exists():
            continue

        try:
            problems.append((common.load_metadata(metadata_file), problem_dir))

        except common.ToolError as error:
            print(f"⚠️ {error}")

    if not problems:
        print("No problems found. Run: python3 tools/new_problem.py")
        return

    print()

    print(
        f"{'#':<4}{'Problem':<30}{'Difficulty':<12}"
        f"{'Status':<15}{'Attempts':<10}"
    )

    print("-" * 71)

    for index, (metadata, problem_dir) in enumerate(problems, start=1):

        problem = str(metadata.get("problem") or problem_dir.name)

        print(
            f"{index:<4}"
            f"{problem[:28]:<30}"
            f"{str(metadata.get('difficulty') or '—'):<12}"
            f"{display_status(metadata.get('status')):<15}"
            f"{common.as_count(metadata.get('attempts')):<10}"
        )

    print()


# ==================================================
# Usage
# ==================================================

def print_usage():

    print("Usage:")
    print("  python3 tools/status.py <action> <problem>")
    print()
    print("Actions:")

    for action in list(ACTIONS) + ["show", "list"]:
        print(f"  {action}")


# ==================================================
# Main
# ==================================================

def main():

    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "list":
        list_problems()
        return

    if action not in ACTIONS and action != "show":
        print(f"❌ Unknown action: {action}")
        print()
        print_usage()
        sys.exit(1)

    if len(sys.argv) < 3:
        raise common.ToolError(
            f"Problem name required for '{action}'.\n"
            f"   Example: python3 tools/status.py {action} twooo-sum"
        )

    problem_dir = common.resolve_problem(sys.argv[2])
    metadata_file = problem_dir / common.METADATA_FILENAME

    if not metadata_file.exists():
        raise common.ToolError(
            f"No {common.METADATA_FILENAME} in "
            f"{common.relative_to_root(problem_dir)}\n"
            "   Run: python3 tools/migrate.py"
        )

    metadata = common.load_metadata(metadata_file)

    if action == "show":
        show_problem(metadata)
        return

    before = (
        common.normalize_status(metadata.get("status")),
        common.as_count(metadata.get("attempts")),
        common.as_count(metadata.get("revisit_count")),
    )

    ACTIONS[action](metadata)

    metadata["last_activity"] = common.today()

    common.save_metadata(metadata_file, metadata)

    # ----------------------------------------------
    # Report what changed
    # ----------------------------------------------

    print()
    print(f"✅ {metadata.get('problem') or problem_dir.name}")

    print(
        f"   Status: {display_status(before[0])} "
        f"→ {display_status(metadata['status'])}"
    )

    if common.as_count(metadata.get("attempts")) != before[1]:
        print(f"   Attempts: {before[1]} → {metadata['attempts']}")

    if common.as_count(metadata.get("revisit_count")) != before[2]:
        print(f"   Revisits: {before[2]} → {metadata['revisit_count']}")

    if action == "solved":
        print(f"   Solved: {metadata['date_solved']}")

    sync_index.sync_index()


if __name__ == "__main__":
    common.run_cli(main)
