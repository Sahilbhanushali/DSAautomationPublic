#!/usr/bin/env python3
"""
Bring older problem folders up to the current layout.

For every problem folder that predates problem.json this recovers what
can be recovered -- from the solution's header comment, from the README
metadata table, from the folder path and from file timestamps -- and
writes the missing files.

Usage:

    python3 tools/migrate.py
    python3 tools/migrate.py --dry-run
    python3 tools/migrate.py <problem>

Nothing that already exists is overwritten. Anything that could not be
determined is left blank and reported, never invented.
"""

from datetime import date
import re
import sys

import common
import new_problem
import sync_index
import sync_readme


# ==================================================
# Recovering metadata
# ==================================================

HEADER_FIELD_RE = re.compile(r"^\s*(\w[\w ]*?)\s*:\s*(.+?)\s*$")

README_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", re.M)

PLACEHOLDERS = ("-", "—", "n/a", "none", "")


def usable(value):
    """True when a recovered value is worth keeping."""

    return common.clean_value(value).lower() not in PLACEHOLDERS


def read_header_fields(solution_file):
    """
    Read the "Key: Value" lines from the top of a solution header.

    These sit between the first two "=====" delimiters:

        ==================================================
        Problem: Two Sum
        Category: Arrays
        ==================================================
    """

    try:
        lines = solution_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()

    except OSError:
        return {}

    delimiters = [
        index
        for index, line in enumerate(lines)
        if common.DELIMITER_RE.match(line)
    ]

    if len(delimiters) < 2:
        return {}

    fields = {}

    for line in lines[delimiters[0] + 1 : delimiters[1]]:

        match = HEADER_FIELD_RE.match(line)

        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()

    return fields


def read_readme_fields(readme_file):
    """Read the README's metadata table into a dictionary."""

    if not readme_file.exists():
        return {}

    try:
        text = readme_file.read_text(encoding="utf-8")

    except OSError:
        return {}

    fields = {}

    for key, value in README_ROW_RE.findall(text):

        key = key.strip().lower()

        if key in ("field", "---"):
            continue

        fields[key] = value.strip()

    return fields


def guess_language(solution_file):
    """Language from the file extension -- always reliable."""

    return {
        ".cpp": "C++",
        ".py": "Python",
        ".java": "Java",
    }.get(solution_file.suffix)


def guess_title(problem_dir):
    """Turn a folder slug into a readable title."""

    return problem_dir.name.replace("-", " ").replace("_", " ").strip().title()


def guess_category(problem_dir):
    """Category from the folder the problem lives in."""

    parent = problem_dir.parent

    if parent == common.PROBLEMS_DIR or parent == parent.parent:
        return "Other"

    return parent.name.replace("-", " ").replace("_", " ").title()


def oldest_date(problem_dir):
    """The earliest file timestamp in the folder, as an ISO date."""

    times = [
        path.stat().st_mtime
        for path in problem_dir.iterdir()
        if path.is_file()
    ]

    if not times:
        return common.today()

    return date.fromtimestamp(min(times)).isoformat()


def pick(*values):
    """First usable value, or an empty string."""

    for value in values:
        if usable(value):
            return common.clean_value(value)

    return ""


def recover_metadata(problem_dir, solution_file, notes):
    """
    Build a problem.json from whatever the folder already tells us.

    Fields that cannot be determined are left empty and appended to
    `notes` so the user can fill them in.
    """

    header = read_header_fields(solution_file) if solution_file else {}
    readme = read_readme_fields(problem_dir / common.README_FILENAME)

    title = pick(header.get("problem"), readme.get("problem"))

    if not title:
        title = guess_title(problem_dir)
        notes.append(f'problem name guessed from the folder name: "{title}"')

    category = pick(header.get("category"), readme.get("category"))

    if not category:
        category = guess_category(problem_dir)
        notes.append(f'category guessed from the folder path: "{category}"')

    difficulty = pick(header.get("difficulty"), readme.get("difficulty"))

    if not difficulty:
        notes.append('"difficulty" is unknown -- fill it in')

    source = pick(header.get("source"), readme.get("source"))

    if not source:
        notes.append('"source" is unknown -- fill it in')

    language = guess_language(solution_file) if solution_file else ""

    if not language:
        notes.append('"language" is unknown -- fill it in')

    url = pick(readme.get("problem url"), header.get("url"))

    approaches = recover_approaches(solution_file)

    metadata = common.new_metadata(
        problem=title,
        category=category,
        difficulty=difficulty,
        language=language,
        source=source,
        url=url or None,
        approaches=approaches,
    )

    metadata["date_added"] = oldest_date(problem_dir)

    # Status is inferred from the file only, and only ever forward.
    # Whether an online judge accepted it is not knowable from here.

    if solution_file and common.has_meaningful_code(solution_file):
        metadata["status"] = common.IN_PROGRESS
        metadata["last_activity"] = metadata["date_added"]

    return metadata


def recover_approaches(solution_file):
    """Approach names from the solution header, when it lists any."""

    if solution_file is None:
        return []

    try:
        parsed = sync_readme.parse_solution(
            solution_file.read_text(encoding="utf-8", errors="replace")
        )

    except OSError:
        return []

    if not parsed:
        return []

    return [approach["name"] for approach in parsed["approaches"]]


# ==================================================
# Repairing README.md
# ==================================================

GENERATED_BODIES = (
    "> Write the problem statement here.",
    "_No approaches defined in the solution file._",
)

MARKER_SECTIONS = (
    ("Problem", common.PROBLEM_START, common.PROBLEM_END),
    ("Approaches", common.APPROACHES_START, common.APPROACHES_END),
)


def is_generated_body(body):
    """True when a section body is tool output we may safely replace."""

    body = body.strip()

    return (
        not body
        or body in GENERATED_BODIES
        or body.startswith("| # | Approach |")
    )


def insert_markers(text, heading, start, end, notes):
    """
    Add a missing marker pair under one README heading.

    Generated placeholder text is dropped; anything the user wrote is
    kept below the markers and reported, so nothing is ever lost.
    """

    if start in text and end in text:
        return text

    pattern = re.compile(
        rf"^(##\s+{re.escape(heading)}\s*\n)(.*?)(?=^---\s*$|^##\s|\Z)",
        re.M | re.S,
    )

    match = pattern.search(text)
    block = f"\n{start}\n{end}\n\n"

    if not match:
        notes.append(
            f'README.md: appended a "## {heading}" section at the end '
            "-- move it wherever you like"
        )
        return text.rstrip("\n") + f"\n\n---\n\n## {heading}\n{block}"

    body = match.group(2)

    if is_generated_body(body):
        replacement = match.group(1) + block
    else:
        notes.append(
            f'README.md: kept your existing "## {heading}" text below '
            "the sync markers -- move or delete it if you don't want it"
        )
        replacement = match.group(1) + block + body.strip() + "\n\n"

    notes.append(f"README.md: added {heading.upper()} sync markers")

    return text[: match.start()] + replacement + text[match.end() :]


def repair_readme(problem_dir, metadata, notes, dry_run):
    """Create a missing README, or add missing markers to an existing one."""

    readme_file = problem_dir / common.README_FILENAME

    if not readme_file.exists():

        notes.append("README.md created")

        if dry_run:
            return

        readme_file.write_text(
            new_problem.README_TEMPLATE.format(
                problem=metadata["problem"],
                category=metadata["category"] or "-",
                difficulty=metadata["difficulty"] or "-",
                language=metadata["language"] or "-",
                source=metadata["source"] or "-",
                url=metadata["url"] or "-",
            ),
            encoding="utf-8",
        )

        return

    try:
        text = readme_file.read_text(encoding="utf-8")

    except OSError as error:
        notes.append(f"README.md could not be read: {error}")
        return

    updated = text

    for heading, start, end in MARKER_SECTIONS:
        updated = insert_markers(updated, heading, start, end, notes)

    if updated != text and not dry_run:
        readme_file.write_text(updated, encoding="utf-8")


# ==================================================
# Migrating one problem
# ==================================================

def migrate_problem(problem_dir, dry_run):
    """
    Migrate one folder.

    Returns a list of notes -- empty when there was nothing to do.
    """

    notes = []

    metadata_file = problem_dir / common.METADATA_FILENAME
    solution_file = common.find_solution_file(problem_dir)

    if solution_file is None:
        notes.append("no solution file -- add one by hand")

    if metadata_file.exists():
        metadata = common.load_metadata(metadata_file)
    else:
        metadata = recover_metadata(problem_dir, solution_file, notes)

        notes.insert(0, f"{common.METADATA_FILENAME} created")

        if not dry_run:
            common.save_metadata(metadata_file, metadata)

    repair_readme(problem_dir, metadata, notes, dry_run)

    return notes


# ==================================================
# Main
# ==================================================

def main():

    arguments = [argument for argument in sys.argv[1:] if argument != "--dry-run"]

    dry_run = "--dry-run" in sys.argv

    if arguments:
        problem_dirs = [common.resolve_problem(arguments[0])]
    else:
        problem_dirs = common.iter_problem_dirs()

    print()
    print("DSA Migration" + (" (dry run)" if dry_run else ""))
    print()

    if not problem_dirs:
        print("No problems found.")
        print()
        return

    migrated = 0

    for problem_dir in problem_dirs:

        notes = migrate_problem(problem_dir, dry_run)

        if not notes:
            continue

        migrated += 1

        print(f"• {common.relative_to_root(problem_dir)}")

        for note in notes:
            print(f"    {note}")

        print()

    if not migrated:
        print("Everything is already up to date.")
        print()
        return

    if dry_run:
        print(f"{migrated} problems would change. Nothing was written.")
        print()
        return

    # Fill the new READMEs and rebuild the index.

    for problem_dir in problem_dirs:
        sync_readme.sync_problem(
            problem_dir, quiet=True, update_index=False, record=False
        )

    sync_index.sync_index()

    print(f"{migrated} problems migrated.")
    print()
    print("Review the reported fields, then run: python3 tools/check.py")
    print()


if __name__ == "__main__":
    common.run_cli(main)
