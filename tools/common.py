#!/usr/bin/env python3
"""
Shared helpers for the DSA tooling.

Everything the other scripts agree on lives here: repository paths, the
problem.json schema, the README/index markers, and the conservative
activity tracking that turns real user actions into metadata.

Nothing in this module prompts, and nothing here calls sys.exit() except
fail(), so the individual tools stay in charge of their own output.
"""

from datetime import date
from pathlib import Path
import json
import re
import sys


# ==================================================
# Paths
# ==================================================

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent

PROBLEMS_DIR = ROOT / "problems"
INDEX_FILE = ROOT / "PROBLEMS.md"

METADATA_FILENAME = "problem.json"
README_FILENAME = "README.md"
INPUT_FILENAME = "input.txt"

SOLUTION_EXTENSIONS = (".cpp", ".py", ".java")


# ==================================================
# Status model
# ==================================================

NOT_STARTED = "not_started"
IN_PROGRESS = "in_progress"
SOLVED = "solved"
REVISIT = "revisit"

VALID_STATUSES = (NOT_STARTED, IN_PROGRESS, SOLVED, REVISIT)

STATUS_LABELS = {
    NOT_STARTED: "Not Started",
    IN_PROGRESS: "In Progress",
    SOLVED: "Solved",
    REVISIT: "Revisit",
}

# Statuses that automatic transitions are allowed to leave.
# Anything else was set deliberately and is never touched by automation.
AUTO_PROMOTABLE = (NOT_STARTED,)


# ==================================================
# Markers
# ==================================================

PROBLEM_START = "<!-- SYNC:PROBLEM:START -->"
PROBLEM_END = "<!-- SYNC:PROBLEM:END -->"

APPROACHES_START = "<!-- SYNC:APPROACHES:START -->"
APPROACHES_END = "<!-- SYNC:APPROACHES:END -->"

INDEX_START = "<!-- INDEX:START -->"
INDEX_END = "<!-- INDEX:END -->"

DELIMITER_RE = re.compile(r"^\s*={5,}\s*$")


# ==================================================
# Errors
# ==================================================

class ToolError(Exception):
    """A problem the user can fix. Printed as a message, never a traceback."""


def fail(message):
    """Print a user-facing error and exit with a non-zero status."""

    print(f"❌ {message}")
    sys.exit(1)


def run_cli(main_function):
    """
    Run a tool's main() with friendly handling of the usual interruptions.

    Genuine programming errors still raise, so bugs stay visible.
    """

    try:
        main_function()

    except ToolError as error:
        fail(str(error))

    except (KeyboardInterrupt, EOFError):
        print("\n\nCancelled.")
        sys.exit(130)


# ==================================================
# Small formatting helpers
# ==================================================

def today():
    """Today's date as an ISO string."""

    return date.today().isoformat()


def clean_value(value):
    """Normalize a metadata value into a trimmed string."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def table_cell(value):
    """Make a value safe to drop into a Markdown table cell."""

    value = clean_value(value)

    if not value:
        return "—"

    return value.replace("|", "\\|").replace("\n", " ")


def normalize_status(status):
    """Return a lowercase status, defaulting to not_started."""

    status = clean_value(status).lower()

    return status or NOT_STARTED


def display_status(status):
    """Convert an internal status into its readable label."""

    status = normalize_status(status)

    return STATUS_LABELS.get(status, status.replace("_", " ").title())


def as_count(value):
    """Coerce a counter field into a non-negative integer."""

    if isinstance(value, bool) or not isinstance(value, int):
        return 0

    return max(value, 0)


def replace_between(text, start, end, content):
    """
    Replace everything between two marker lines.

    Returns None when the markers are missing, so callers can report it
    instead of silently rewriting a file they don't own.
    """

    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        re.DOTALL,
    )

    if not pattern.search(text):
        return None

    return pattern.sub(
        lambda _: f"{start}\n{content}\n{end}",
        text,
        count=1,
    )


def write_if_changed(path, content):
    """
    Write a file only when its content actually differs.

    Keeps every sync idempotent and stops save hooks from ping-ponging.
    """

    try:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return False

        path.write_text(content, encoding="utf-8")
        return True

    except OSError as error:
        raise ToolError(f"Could not write {path}: {error}") from error


# ==================================================
# problem.json
# ==================================================

def load_metadata(metadata_file):
    """Read and validate a problem.json into a dictionary."""

    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

    except OSError as error:
        raise ToolError(f"Could not read {metadata_file}: {error}") from error

    except json.JSONDecodeError as error:
        raise ToolError(f"Invalid JSON in {metadata_file}: {error}") from error

    if not isinstance(metadata, dict):
        raise ToolError(f"Invalid metadata format in {metadata_file}")

    return metadata


def save_metadata(metadata_file, metadata):
    """Write a problem.json, only when something changed."""

    content = json.dumps(metadata, indent=4, ensure_ascii=False) + "\n"

    return write_if_changed(metadata_file, content)


def new_metadata(problem, category, difficulty, language,
                 source, url, approaches):
    """
    Build a fresh problem.json payload.

    This is the canonical schema; every tool reads through .get() so
    older files without the activity fields keep working untouched.
    """

    return {
        "problem": problem,
        "category": category,
        "difficulty": difficulty,
        "language": language,
        "source": source,
        "url": url,
        "approaches": list(approaches),
        "status": NOT_STARTED,
        "attempts": 0,
        "date_added": today(),
        "date_solved": None,
        "revisit_count": 0,
        "last_activity": None,
        "last_tested": None,
        "last_test_result": None,
    }


# ==================================================
# Locating problems
# ==================================================

def find_solution_file(problem_dir):
    """
    Return the solution file for a problem folder.

    Prefers solution.* and otherwise falls back to the first source file,
    which is how the older <problem-slug>.cpp layout keeps working.
    """

    try:
        candidates = sorted(
            path
            for path in problem_dir.iterdir()
            if path.is_file() and path.suffix in SOLUTION_EXTENSIONS
        )

    except OSError:
        return None

    for path in candidates:
        if path.stem == "solution":
            return path

    return candidates[0] if candidates else None


def is_problem_dir(path):
    """A folder counts as a problem once it holds any of the three files."""

    if not path.is_dir():
        return False

    return (
        (path / METADATA_FILENAME).exists()
        or (path / README_FILENAME).exists()
        or find_solution_file(path) is not None
    )


def is_inside_problems(directory):
    """
    True when a directory sits strictly inside problems/.

    The guard that keeps an editor-driven command on the problem you are
    actually looking at: tools/ holds .py files and the repository root
    holds a README.md, so without this both would pass for problems.
    """

    try:
        relative = Path(directory).resolve().relative_to(PROBLEMS_DIR.resolve())

    except (ValueError, OSError):
        return False

    return relative != Path(".")


def iter_problem_dirs():
    """Yield every problem folder under problems/, sorted by path."""

    if not PROBLEMS_DIR.exists():
        return []

    return sorted(
        path
        for path in PROBLEMS_DIR.rglob("*")
        if is_problem_dir(path)
    )


def resolve_problem(target):
    """
    Turn a CLI argument into a problem folder.

    Accepts a folder path, a file inside the folder, or a bare slug such
    as "two-sum". Raises ToolError with a helpful message otherwise.

    A path is only ever resolved inside problems/, so an editor command
    fired with the wrong file open fails loudly instead of acting on
    something else.
    """

    target = str(target).strip()

    if not target:
        raise ToolError(
            "No problem given.\n"
            "   Open a solution file, or pass a problem name."
        )

    path = Path(target)

    if path.exists():
        directory = path.parent if path.is_file() else path

        directory = directory.resolve()

        if not is_inside_problems(directory):
            raise ToolError(
                f"{relative_to_root(directory)} is not a problem folder.\n"
                "   Open a file inside problems/<category>/<problem>/ first."
            )

        if not is_problem_dir(directory):
            raise ToolError(f"Not a problem folder: {target}")

        return directory

    matches = [
        directory
        for directory in iter_problem_dirs()
        if directory.name.lower() == target.lower()
    ]

    if not matches:
        raise ToolError(
            f"Problem not found: {target}\n"
            "   Run: python3 tools/status.py list"
        )

    if len(matches) > 1:
        listing = "\n".join(f"   {match}" for match in matches)

        raise ToolError(
            f"Multiple problems named '{target}':\n{listing}\n"
            "   Pass the folder path instead."
        )

    return matches[0]


def relative_to_root(path):
    """Display a path relative to the repository root when possible."""

    try:
        return path.relative_to(ROOT).as_posix()

    except ValueError:
        return str(path)


# ==================================================
# Detecting real work in a solution file
# ==================================================

# A line is "boilerplate" when new_problem.py could have written it.
# Everything that survives these filters is something the user typed.

_COMMENT_RE = re.compile(r'^\s*(//|#|\*|/\*|\*/|"""|\'\'\')')

_STRUCTURAL_RE = re.compile(r"^[\s{}()\[\];:]*$")

_BOILERPLATE_RE = re.compile(
    r"""^\s*(
          \#include\b
        | import\b
        | package\b
        | using\s+namespace\b
        | (?:public\s+|private\s+|protected\s+|final\s+|abstract\s+)*class\b
        | (?:public|private|protected)\s*:\s*$
        | def\s+\w+\s*\([^)]*\)\s*(?:->\s*[\w\[\], .]+)?\s*:\s*$
        # A method signature: "void solve() {", "static int f(int n)".
        # The lookahead keeps statements such as "return sorted(x)" out.
        | (?!(?:return|if|elif|else|for|while|switch|case|do|try|catch
             |throw|raise|new|delete|yield|assert|del|with|lambda|print)\b)
          (?:[\w<>,\[\]*&:~]+\s+)+\w+\s*\([^)]*\)\s*(?:const\s*)?\{?\s*$
        | return\s+0\s*;\s*$
        | pass\s*$
        | if\s+__name__\s*==
        | \w+\s*=\s*Solution\s*\(\s*\)\s*$
    )""",
    re.VERBOSE,
)


def strip_header(lines):
    """Drop the generated header comment, keeping only the code region."""

    delimiters = [
        index
        for index, line in enumerate(lines)
        if DELIMITER_RE.match(line)
    ]

    if len(delimiters) >= 3:
        return lines[delimiters[2] + 1:]

    return lines


def has_meaningful_code(solution_file):
    """
    True when the solution file contains code the user actually wrote.

    Deliberately conservative: includes, class and method signatures,
    empty bodies and comments all count as scaffolding, so a freshly
    generated file never looks like work in progress. Missing data is
    better than wrong data.
    """

    try:
        text = solution_file.read_text(encoding="utf-8", errors="replace")

    except OSError:
        return False

    return any(
        line.strip()
        and not _COMMENT_RE.match(line)
        and not _STRUCTURAL_RE.match(line)
        and not _BOILERPLATE_RE.match(line)
        for line in strip_header(text.splitlines())
    )


# ==================================================
# Activity tracking
# ==================================================

def _promote(metadata):
    """
    Move a problem forward, never backward.

    Returns True when the status changed. A solved or revisit problem is
    left alone: only a deliberate command may move it.
    """

    if normalize_status(metadata.get("status")) not in AUTO_PROMOTABLE:
        return False

    metadata["status"] = IN_PROGRESS
    return True


def record_save(problem_dir):
    """
    Record that a solution file was saved with real code in it.

    Returns a short description of what changed, or None when there was
    nothing worth recording (empty scaffold, or a legacy folder without
    problem.json).
    """

    metadata_file = problem_dir / METADATA_FILENAME

    if not metadata_file.exists():
        return None

    solution_file = find_solution_file(problem_dir)

    if solution_file is None or not has_meaningful_code(solution_file):
        return None

    metadata = load_metadata(metadata_file)

    promoted = _promote(metadata)
    metadata["last_activity"] = today()

    if not save_metadata(metadata_file, metadata):
        return None

    return "started" if promoted else None


def record_run(problem_dir, passed):
    """
    Record that a solution was executed.

    This is the only automatic source of attempts: running code is a real
    attempt, saving a file is not. A passing local run never implies the
    problem is solved -- only an online judge can decide that.
    """

    metadata_file = problem_dir / METADATA_FILENAME

    if not metadata_file.exists():
        return None

    metadata = load_metadata(metadata_file)

    metadata["attempts"] = as_count(metadata.get("attempts")) + 1
    metadata["last_tested"] = today()
    metadata["last_test_result"] = "passed" if passed else "failed"
    metadata["last_activity"] = today()

    promoted = _promote(metadata)

    save_metadata(metadata_file, metadata)

    return {
        "attempts": metadata["attempts"],
        "promoted": promoted,
        "status": metadata["status"],
    }
