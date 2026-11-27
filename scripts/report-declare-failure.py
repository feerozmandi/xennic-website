#!/usr/bin/env python3
"""Say, in the run itself, what a failed Declare verification stopped on.

    python3 scripts/report-declare-failure.py <file> [<file> ...]

WHY THIS EXISTS. A failing CI job that only says "exit code 1" is a job
that has to be read to be understood, and the thing to read is an artefact
that has to be downloaded first. This puts the evidence in the run, as an
annotation the run's own page shows and the check run's API returns, so
the reason is there to be read without anything else being fetched.

One annotation per file: the text is escaped into a single message rather
than split into a line each, because a run's page shows a handful of
annotations and the line that matters must not be the one that was cut.

Nothing here decides anything: the exit status of the check that failed is
left alone, and this script always succeeds.
"""

from __future__ import annotations

import pathlib
import sys

# How many lines of each file are shown, and how long one line may be. The
# end of a log is where a run stopped, so the end is what is wanted.
TAIL_LINES = 80
MAX_LINE = 800
MAX_MESSAGE = 60_000


def escape(text: str) -> str:
    """Text, made safe to be a workflow command's message."""
    return (
        text.replace("\r", "")
        .replace("%", "%25")
        .replace("\n", "%0A")
        .replace(":", "%3A")
    )


def report(path: pathlib.Path) -> None:
    print(f"::error title=The Declare verification stopped::file `{path.name}`")
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as error:
        print(f"::error::{escape(f'{path.name} could not be read: {error}')}")
        return
    if not lines:
        print(f"::error::{escape(f'{path.name} is empty.')}")
        return
    tail = lines[-TAIL_LINES:]
    if len(lines) > len(tail):
        tail.insert(0, f"… {len(lines) - len(tail)} earlier lines are not shown.")
    body = []
    for line in tail:
        if len(line) > MAX_LINE:
            line = line[: MAX_LINE - 1] + "…"
        body.append(line)
    message = "\n".join(body)
    if len(message) > MAX_MESSAGE:
        message = message[: MAX_MESSAGE - 1] + "…"
    print(f"::error::{escape(message)}")


def main(argv: list[str]) -> int:
    if not argv:
        print("::error::No file to report was named.")
        return 0
    for name in argv:
        report(pathlib.Path(name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
