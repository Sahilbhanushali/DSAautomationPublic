# DSA Practice Repository

Local practice log. The tooling does the bookkeeping so the only thing
left to do is solve problems.

See [PROBLEMS.md](PROBLEMS.md) for the generated index.

## Workflow

```
python3 tools/new_problem.py     ->  folder, solution stub, README, problem.json
write code                       ->
Ctrl+S                           ->  README + PROBLEMS.md sync, Not Started -> In Progress
Ctrl+Shift+B  (or run.py)        ->  compile, run, record the attempt
submit to the judge              ->
python3 tools/status.py solved <problem>
```

Only the last step is manual, and deliberately so: a local run passing
says nothing about whether the judge accepted the answer.

## Layout

```
problems/<category>/<problem-slug>/
    solution.cpp | solution.py | <Class>.java   your code, plus a header comment
    README.md                                   documentation (yours, outside the markers)
    problem.json                                metadata (the source of truth)
    input.txt                                   optional, fed to the program on stdin
```

`problem.json` is what every tool reads and writes. `README.md` is for
you; only the regions between the `<!-- SYNC:... -->` markers are
generated. `PROBLEMS.md` is generated entirely from `problem.json`.

## Commands

| Command | What it does |
|---|---|
| `python3 tools/new_problem.py` | Create a problem and open it in VS Code |
| `python3 tools/run.py [problem]` | Compile and run the solution, record the attempt |
| `python3 tools/sync_readme.py [problem]` | Copy the solution header into README.md |
| `python3 tools/sync_index.py` | Rebuild PROBLEMS.md |
| `python3 tools/check.py [problem]` | Validate metadata, docs and markers (non-zero exit on failure) |
| `python3 tools/migrate.py [--dry-run]` | Backfill problem.json / README.md for older folders |
| `python3 tools/status.py <action> <problem>` | Manual override: `start attempt solved revisit reset show list` |
| `python3 tools/test_tools.py` | Self-check for the tooling |

`[problem]` accepts a slug (`two-sum`), a folder, or a file path.
Omitting it means "everything" for the sync tools and "the current
folder" for `run.py`.

## What updates itself

| Event | Effect |
|---|---|
| Problem created | `not_started`, `attempts: 0`, `date_added` |
| Solution saved with real code in it | `not_started` -> `in_progress`, `last_activity` |
| Solution run | `attempts + 1`, `last_tested`, `last_test_result` |
| Any metadata change | `PROBLEMS.md` regenerated |

What does **not** happen automatically: nothing ever moves a problem
back, a solved or revisit problem is never touched by a save, saving
does not count as an attempt, and a passing local run never sets
`solved`. Missing data beats wrong data.

## VS Code

Everything is a task in `.vscode/tasks.json` — a thin layer that shells
out to `tools/*.py`. No extension of our own, no duplicated logic.

Reach them from the Command Palette: `Ctrl+Shift+P` → **Tasks: Run
Task** → pick a `DSA:` task. Or use the shortcut.

| Shortcut | Task | Acts on |
|---|---|---|
| `Ctrl+Alt+N` | DSA: New Problem | — |
| `Ctrl+Alt+R` | DSA: Run Current Problem | open file |
| `Ctrl+Alt+S` | DSA: Sync Current Problem | open file |
| `Ctrl+Alt+D` | DSA: Mark Solved | open file |
| `Ctrl+Alt+L` | DSA: Mark Revisit | open file |
| `Ctrl+Alt+I` | DSA: Show Status | open file |
| `Ctrl+Alt+K` | DSA: Validate Repository | whole repo |
| `Ctrl+Shift+B` | DSA: Run Current Problem (default build task) | open file |

No shortcut, palette only: *DSA: Validate Current Problem*, *DSA: List
Problems*, *DSA: Sync All Problems*, *DSA: Migrate Old Problems*.

**Current problem detection.** Tasks pass `${file}` — whatever is open
in the editor — and `tools/common.resolve_problem()` turns it into a
problem folder. Any file in the folder works: the solution, the README,
or `problem.json`. Paths outside `problems/` are refused outright, so a
shortcut pressed while `tools/run.py` or the root `README.md` is open
fails with a message instead of acting on the wrong thing.

**Automatic save sync.** `emeraldwalk.RunOnSave` handles it, configured
in `.vscode/settings.json`: saving a solution syncs its README, promotes
Not Started to In Progress and rebuilds `PROBLEMS.md`; saving a
`problem.json` by hand rebuilds `PROBLEMS.md`. Nothing else triggers, so
there is no sync loop. Without the extension nothing breaks — use
`Ctrl+Alt+S` or run `python3 tools/sync_readme.py` occasionally.

Shortcuts live in your user `keybindings.json`, not the workspace (VS
Code has no workspace-level keybindings), so they are visible in other
projects; firing one there just reports that the task does not exist.

## Notes

- Python 3, standard library only. `g++` is needed for C++ and
  `javac`/`java` for Java.
- C++ and Java build into a temporary directory, so no binaries or
  `.class` files are left in the problem folders.
- Online judge submission is not automated. Nothing here stores
  credentials, cookies or tokens.
