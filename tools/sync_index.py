#!/usr/bin/env python3
"""
Generate and maintain the global DSA problem index.

Creates:
    PROBLEMS.md

Problem metadata is read from:
    problems/**/problem.json

Usage:

    python3 tools/sync_index.py

    python3 tools/sync_index.py --check

The script preserves everything outside the generated section
between the INDEX markers.
"""

from pathlib import Path
import sys

import common


# ==================================================
# Configuration
# ==================================================

ROOT = common.ROOT
PROBLEMS_DIR = common.PROBLEMS_DIR
INDEX_FILE = common.INDEX_FILE

METADATA_FILENAME = common.METADATA_FILENAME

INDEX_START = common.INDEX_START
INDEX_END = common.INDEX_END

clean_value = common.clean_value
table_cell = common.table_cell
display_status = common.display_status
normalize_status = common.normalize_status


# ==================================================
# Helpers
# ==================================================

def problem_slug_from_path(problem_dir):
    """
    Return a problem's relative path from the problems directory.

    Example:

        problems/arrays/two-sum

    becomes:

        arrays/two-sum
    """

    return problem_dir.relative_to(PROBLEMS_DIR)


def markdown_link(text, path):
    """
    Create a relative Markdown link from PROBLEMS.md.
    """

    relative_path = Path("problems") / path

    return f"[{text}]({relative_path.as_posix()})"


# ==================================================
# Finding Problems
# ==================================================

def find_problem_metadata():
    """
    Find every problem.json inside problems/.
    """

    if not PROBLEMS_DIR.exists():
        return []

    return sorted(
        path
        for path in PROBLEMS_DIR.rglob(METADATA_FILENAME)
        if path.is_file()
    )


# ==================================================
# Problem Parsing
# ==================================================

def parse_problem(metadata_file):
    """
    Read and normalize one problem.json.

    Returns None (with a warning) when the file cannot be read or has no
    problem name, so one broken file never stops the whole index.
    """

    try:
        metadata = common.load_metadata(metadata_file)

    except common.ToolError as error:
        print(f"⚠️ {error}")
        return None

    problem = clean_value(metadata.get("problem"))

    if not problem:
        print(f"⚠️ Missing 'problem' in {metadata_file}")
        return None

    approaches = metadata.get("approaches", [])

    if not isinstance(approaches, list):
        approaches = []

    approaches = [
        clean_value(approach)
        for approach in approaches
        if clean_value(approach)
    ]

    return {
        "title": problem,
        "category": clean_value(metadata.get("category", "Other")) or "Other",
        "difficulty": clean_value(metadata.get("difficulty", "—")) or "—",
        "language": clean_value(metadata.get("language", "—")) or "—",
        "source": clean_value(metadata.get("source", "—")) or "—",
        "url": clean_value(metadata.get("url", "")),
        "approaches": approaches,
        "status": normalize_status(metadata.get("status", common.NOT_STARTED)),
        "attempts": common.as_count(metadata.get("attempts", 0)),
        "date_added": clean_value(metadata.get("date_added", "")),
        "date_solved": clean_value(metadata.get("date_solved", "")),
        "revisit_count": common.as_count(metadata.get("revisit_count", 0)),
        "path": problem_slug_from_path(metadata_file.parent),
    }


def load_problems():
    """
    Load all problems from problem.json files.
    """

    problems = []

    for metadata_file in find_problem_metadata():

        problem = parse_problem(metadata_file)

        if problem is not None:
            problems.append(problem)

    return problems


# ==================================================
# Rendering
# ==================================================

def render_problem_row(problem):
    """
    Render one Markdown table row.
    """

    title = markdown_link(
        table_cell(problem["title"]),
        problem["path"],
    )

    approaches = (
        ", ".join(problem["approaches"])
        if problem["approaches"]
        else "—"
    )

    return (
        f"| {title} "
        f"| {table_cell(problem['difficulty'])} "
        f"| {display_status(problem['status'])} "
        f"| {problem['attempts']} "
        f"| {table_cell(problem['source'])} "
        f"| {table_cell(approaches)} |"
    )


def render_category(category, problems):
    """
    Render one category section.
    """

    lines = [
        f"## {category}",
        "",
        "| Problem | Difficulty | Status | Attempts | Source | Approaches |",
        "|---|---|---|---:|---|---|",
    ]

    for problem in problems:
        lines.append(render_problem_row(problem))

    lines.append("")

    return "\n".join(lines)


def count_difficulty(problems, difficulty):
    """Count problems of one difficulty, ignoring case."""

    return sum(
        1
        for problem in problems
        if problem["difficulty"].lower() == difficulty
    )


def count_status(problems, status):
    """Count problems in one status."""

    return sum(1 for problem in problems if problem["status"] == status)


def group_by_category(problems):
    """Group problems by category, each category sorted by title."""

    grouped = {}

    for problem in problems:
        grouped.setdefault(problem["category"], []).append(problem)

    return {
        category: sorted(
            grouped[category],
            key=lambda problem: problem["title"].lower(),
        )
        for category in sorted(grouped, key=str.lower)
    }


def render_index(problems):
    """
    Generate the complete synchronized index section.
    """

    if not problems:
        return "_No problems found yet._"

    lines = [
        f"**Total Problems:** {len(problems)}",
        "",
        "### Difficulty",
        "",
        f"- Easy: **{count_difficulty(problems, 'easy')}**",
        f"- Medium: **{count_difficulty(problems, 'medium')}**",
        f"- Hard: **{count_difficulty(problems, 'hard')}**",
        "",
        "### Status",
        "",
        f"- Not Started: **{count_status(problems, common.NOT_STARTED)}**",
        f"- In Progress: **{count_status(problems, common.IN_PROGRESS)}**",
        f"- Solved: **{count_status(problems, common.SOLVED)}**",
        f"- Revisit: **{count_status(problems, common.REVISIT)}**",
        "",
    ]

    for category, category_problems in group_by_category(problems).items():
        lines.append(render_category(category, category_problems))

    return "\n".join(lines).rstrip()


# ==================================================
# Index File Handling
# ==================================================

def create_initial_index():
    """
    Create PROBLEMS.md if it doesn't exist.
    """

    content = f"""# DSA Problems

This file is automatically maintained by `tools/sync_index.py`.

Do not manually edit anything between the index markers.

{INDEX_START}

{INDEX_END}
"""

    common.write_if_changed(INDEX_FILE, content)


def replace_index_section(text, content):
    """
    Replace everything between INDEX_START and INDEX_END.
    """

    return common.replace_between(
        text,
        INDEX_START,
        INDEX_END,
        f"\n{content}\n",
    )


# ==================================================
# Main Sync Logic
# ==================================================

def sync_index(check_only=False, quiet=False):
    """
    Generate or update PROBLEMS.md.

    Returns True when the index is (or was made) up to date.
    """

    problems = load_problems()

    if not INDEX_FILE.exists():

        if check_only:
            print("❌ PROBLEMS.md does not exist.")
            return False

        create_initial_index()

    try:
        current = INDEX_FILE.read_text(encoding="utf-8")

    except OSError as error:
        print(f"❌ Could not read {INDEX_FILE}: {error}")
        return False

    updated = replace_index_section(current, render_index(problems))

    if updated is None:
        print("❌ PROBLEMS.md is missing INDEX markers.")
        print()
        print("Required markers:")
        print(f"  {INDEX_START}")
        print(f"  {INDEX_END}")
        return False

    if updated == current:

        if not quiet:
            print(
                f"✔️  PROBLEMS.md already up to date "
                f"({len(problems)} problems)"
            )

        return True

    if check_only:
        print("❌ PROBLEMS.md is out of date.")
        return False

    common.write_if_changed(INDEX_FILE, updated)

    if not quiet:
        print(f"✅ PROBLEMS.md updated ({len(problems)} problems)")

    return True


# ==================================================
# Entry Point
# ==================================================

def main():

    check_only = "--check" in sys.argv

    if not sync_index(check_only=check_only):
        sys.exit(1)


if __name__ == "__main__":
    common.run_cli(main)
