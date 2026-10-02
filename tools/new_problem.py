#!/usr/bin/env python3
"""
Scaffold a new DSA problem folder with a solution file and a README.

Usage:
    python3 tools/new_problem.py

Creates:
    problems/<category>/<problem-slug>/
        solution.<ext>   (or <ClassName>.java for Java)
        README.md

After writing your solution, run:
    python3 tools/sync_readme.py <problem-folder>
to copy the Problem and Approach notes into the README.
"""

import re
import shutil
import subprocess

import common
from sync_readme import sync_problem


# ==================================================
# Configuration
# ==================================================

TOOLS_DIR = common.TOOLS_DIR
ROOT = common.ROOT
PROBLEMS_DIR = common.PROBLEMS_DIR
PROBLEM_METADATA_FILENAME = common.METADATA_FILENAME

CATEGORIES = [
    "Arrays",
    "Strings",
    "Hashing",
    "Two Pointers",
    "Sliding Window",
    "Binary Search",
    "Linked List",
    "Stack",
    "Queue",
    "Recursion",
    "Backtracking",
    "Trees",
    "Graphs",
    "Heap",
    "Greedy",
    "Dynamic Programming",
    "Math",
    "Bit Manipulation",
    "Other",
]

DIFFICULTIES = ["Easy", "Medium", "Hard"]

LANGUAGES = ["C++", "Python", "Java"]

SOURCES = [
    "LeetCode",
    "GeeksforGeeks",
    "Codeforces",
    "CodeChef",
    "HackerRank",
    "Other",
]

APPROACHES = ["Brute Force", "Better", "Optimal"]

CUSTOM_APPROACH = "Custom (type your own)"


# ==================================================
# Helpers
# ==================================================

def slugify(text):
    """
    Convert a problem name into a filesystem-friendly slug.

    Example:
        "Best Time to Buy & Sell Stock"
        ->
        "best-time-to-buy-sell-stock"
    """
    text = text.strip().lower()

    # Replace anything that is not a letter or number with "-"
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # Remove leading/trailing "-"
    return text.strip("-")


def to_class_name(text):
    """
    Convert a problem name into a valid Java class name.

    Example:
        "2 Sum II - Input Array Is Sorted"
        ->
        "P2SumIiInputArrayIsSorted"
    """
    words = re.findall(r"[A-Za-z0-9]+", text)
    name = "".join(word.capitalize() for word in words)

    if not name:
        return "Solution"

    # Java identifiers cannot start with a digit
    if name[0].isdigit():
        name = "P" + name

    return name


def to_method_name(text, style):
    """
    Convert an approach name into a method name.

    style="snake":  "Brute Force" -> "brute_force"   (Python)
    style="camel":  "Brute Force" -> "bruteForce"    (C++, Java)
    """
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", text)]

    if not words:
        words = ["approach"]

    if style == "snake":
        name = "_".join(words)
    else:
        name = words[0] + "".join(w.capitalize() for w in words[1:])

    if name[0].isdigit():
        name = "approach_" + name if style == "snake" else "approach" + name

    return name


def unique_method_names(approaches, style):
    """Method names for each approach, made unique if two collide."""
    names = []
    seen = {}

    for approach in approaches:
        name = to_method_name(approach, style)
        seen[name] = seen.get(name, 0) + 1

        if seen[name] > 1:
            name = f"{name}{seen[name]}"

        names.append(name)

    return names


def get_input(prompt, default=None, required=True):
    """
    Get input from the user.
    """

    while True:
        if default is not None:
            value = input(f"{prompt} [{default}]: ").strip()

            if not value:
                return default
        else:
            value = input(f"{prompt}: ").strip()

        if value or not required:
            return value

        print("Please enter a value.")


def choose(prompt, options):
    """
    Display numbered options and return the selected option.
    """

    print(f"\n{prompt}")

    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")

    while True:
        choice = input("\nChoose: ").strip()

        if choice.isdigit():
            index = int(choice) - 1

            if 0 <= index < len(options):
                return options[index]

        print("Invalid choice. Please select a valid number.")


def choose_many(prompt, options):
    """
    Display numbered options and return a list of selected options,
    in the order the user typed them. Example input: "1,3" or "1 2 3".
    """

    print(f"\n{prompt}")

    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")

    while True:
        raw = input("\nChoose one or more (e.g. 1,3): ").strip()
        parts = [p for p in re.split(r"[,\s]+", raw) if p]

        if parts and all(p.isdigit() and 1 <= int(p) <= len(options) for p in parts):
            selected = []

            for p in parts:
                option = options[int(p) - 1]
                if option not in selected:
                    selected.append(option)

            return selected

        print("Invalid choice. Enter numbers from the list, separated by commas.")


def choose_approaches():
    """
    Ask which approaches the problem will have.
    Returns a list of approach names, e.g. ["Brute Force", "Optimal"].
    """

    selected = choose_many("Approaches:", APPROACHES + [CUSTOM_APPROACH])
    approaches = []

    for option in selected:
        if option == CUSTOM_APPROACH:
            raw = get_input("Custom approach names (comma-separated)")
            approaches.extend(name.strip() for name in raw.split(",") if name.strip())
        else:
            approaches.append(option)

    return approaches or ["Optimal"]


def confirm(prompt, default=False):
    """
    Ask a yes/no question.
    """

    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix}: ").strip().lower()

    if not answer:
        return default

    return answer in ("y", "yes")


def open_in_vscode(file_path):
    """
    Open the generated solution file in VS Code.
    """

    # shutil.which also finds "code.cmd" on Windows,
    # which a plain Popen(["code", ...]) would miss.
    code_cmd = shutil.which("code")

    if code_cmd is None:
        print(
            "\n⚠️ Could not open VS Code automatically. "
            "Make sure the 'code' command is available in your PATH."
        )
        return

    try:
        subprocess.Popen(
            [code_cmd, str(file_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        print(f"\n⚠️ Could not open VS Code: {error}")


# ==================================================
# Header block (shared by all languages)
# ==================================================
#
# sync_readme.py reads this block. Keep the "=====" lines,
# the "Problem:" line and the "Approach N: <name>" lines as they are.

def build_header(problem, category, difficulty, source, approaches):
    line = "=" * 50

    parts = [
        line,
        f"Problem: {problem}",
        f"Category: {category}",
        f"Difficulty: {difficulty}",
        f"Source: {source}",
        line,
        "",
        "Problem:",
        "",
        "",
    ]

    for number, name in enumerate(approaches, start=1):
        parts += [
            f"Approach {number}: {name}",
            "    Idea:",
            "",
            "    Time:",
            "    Space:",
            "",
        ]

    parts.append(line)
    return "\n".join(parts)


# ==================================================
# Method stubs (one per approach)
# ==================================================

def cpp_methods(approaches):
    names = unique_method_names(approaches, "camel")
    blocks = []

    for number, (approach, name) in enumerate(zip(approaches, names), start=1):
        blocks.append(
            f"    // Approach {number}: {approach}\n"
            f"    void {name}() {{\n"
            f"\n"
            f"    }}"
        )

    return "\n\n".join(blocks)


def python_methods(approaches):
    names = unique_method_names(approaches, "snake")
    blocks = []

    for number, (approach, name) in enumerate(zip(approaches, names), start=1):
        blocks.append(
            f"    # Approach {number}: {approach}\n"
            f"    def {name}(self):\n"
            f"        pass"
        )

    return "\n\n".join(blocks)


def java_methods(approaches):
    names = unique_method_names(approaches, "camel")
    blocks = []

    for number, (approach, name) in enumerate(zip(approaches, names), start=1):
        blocks.append(
            f"    // Approach {number}: {approach}\n"
            f"    static void {name}() {{\n"
            f"\n"
            f"    }}"
        )

    return "\n\n".join(blocks)


# ==================================================
# C++ Template
# ==================================================

CPP_TEMPLATE = """\
/*
{header}
*/

#include <bits/stdc++.h>
using namespace std;


class Solution {{
public:

{methods}

}};


int main() {{

    return 0;
}}
"""


# ==================================================
# Python Template
# ==================================================

PYTHON_TEMPLATE = """\
\"\"\"
{header}
\"\"\"


class Solution:

{methods}


if __name__ == "__main__":
    solution = Solution()
"""


# ==================================================
# Java Template
# ==================================================

JAVA_TEMPLATE = """\
/*
{header}
*/

public class {class_name} {{

{methods}

    public static void main(String[] args) {{

    }}
}}
"""


# ==================================================
# README Template
# ==================================================
#
# Content between the SYNC markers is filled by sync_readme.py.
# Everything outside the markers is yours and is never overwritten.

README_TEMPLATE = """\
# {problem}

## Metadata

| Field | Value |
|---|---|
| Category | {category} |
| Difficulty | {difficulty} |
| Language | {language} |
| Source | {source} |
| Problem URL | {url} |

---

## Problem

<!-- SYNC:PROBLEM:START -->
<!-- SYNC:PROBLEM:END -->

---

## Examples

### Example 1

**Input:**

```text

```

**Output:**

```text

```

**Explanation:**

---

## Constraints

-

---

## Approaches

<!-- SYNC:APPROACHES:START -->
<!-- SYNC:APPROACHES:END -->

---

## Notes

-
"""


# ==================================================
# Language configuration
# ==================================================

LANGUAGE_CONFIG = {
    "C++": {"template": CPP_TEMPLATE, "extension": "cpp", "methods": cpp_methods},
    "Python": {"template": PYTHON_TEMPLATE, "extension": "py", "methods": python_methods},
    "Java": {"template": JAVA_TEMPLATE, "extension": "java", "methods": java_methods},
}


# ==================================================
# Main
# ==================================================

def main():
    print("=" * 50)
    print("  New Problem Generator")
    print("=" * 50)

    problem = get_input("\nProblem name")
    slug = slugify(problem)

    if not slug:
        raise common.ToolError(
            "Problem name must contain at least one letter or number."
        )

    category = choose("Category:", CATEGORIES)
    difficulty = choose("Difficulty:", DIFFICULTIES)
    language = choose("Language:", LANGUAGES)
    approaches = choose_approaches()
    source = choose("Source:", SOURCES)

    if source == "Other":
        source = get_input("Source name")

    url = get_input("Problem URL (optional)", required=False) or None

    problem_dir = PROBLEMS_DIR / slugify(category) / slug

    config = LANGUAGE_CONFIG[language]
    class_name = to_class_name(problem)

    # Java requires the file name to match the public class name
    if language == "Java":
        solution_file = problem_dir / f"{class_name}.java"
    else:
        solution_file = problem_dir / f"solution.{config['extension']}"

    readme_file = problem_dir / "README.md"
    metadata_file = problem_dir / PROBLEM_METADATA_FILENAME

    if solution_file.exists() or readme_file.exists() or metadata_file.exists():
        print(f"\n⚠️ Files already exist in: {problem_dir}")

        if not confirm("Overwrite them?"):
            print("Aborted. Nothing was changed.")
            return

    problem_dir.mkdir(parents=True, exist_ok=True)

    header = build_header(problem, category, difficulty, source, approaches)

    solution_code = config["template"].format(
        header=header,
        methods=config["methods"](approaches),
        class_name=class_name,
    )

    readme = README_TEMPLATE.format(
        problem=problem,
        category=category,
        difficulty=difficulty,
        language=language,
        source=source,
        url=url or "-",
    )

    metadata = common.new_metadata(
        problem=problem,
        category=category,
        difficulty=difficulty,
        language=language,
        source=source,
        url=url,
        approaches=approaches,
    )

    solution_file.write_text(solution_code, encoding="utf-8")
    readme_file.write_text(readme, encoding="utf-8")
    common.save_metadata(metadata_file, metadata)

    # Fill the README's approach sections and refresh PROBLEMS.md.
    # The empty scaffold contains no real code, so the problem stays
    # Not Started until you actually write something.
    sync_problem(problem_dir, quiet=True)

    print("\n✅ Problem created successfully!")
    print(f"   Folder:     {problem_dir.relative_to(ROOT)}")
    print(f"   Solution:   {solution_file.name}")
    print(f"   README:     {readme_file.name}")
    print(f"   Metadata:   {metadata_file.name}")
    print(f"   Approaches: {', '.join(approaches)}")
    print(
        "\n   Saving the solution keeps the README and PROBLEMS.md in sync.\n"
        "   Run and test it with:\n"
        f"   python3 tools/run.py {slug}"
    )

    open_in_vscode(solution_file)


if __name__ == "__main__":
    common.run_cli(main)