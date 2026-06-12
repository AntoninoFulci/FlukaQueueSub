#!/usr/bin/env python3
"""Collect ROOT files from job subdirectories into root_files/."""

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table


@dataclass
class FileMove:
    parent_dir: Path
    job_dir: Path
    source: Path
    dest: Path
    size: int


@dataclass
class EmptyJob:
    parent_dir: Path
    job_dir: Path


@dataclass
class MovePlan:
    moves: list[FileMove] = field(default_factory=list)
    empty_jobs: list[EmptyJob] = field(default_factory=list)
    skipped_parents: list[Path] = field(default_factory=list)


def scan_all(cwd: Path) -> MovePlan:
    plan = MovePlan()
    for parent_dir in sorted(p for p in cwd.iterdir() if p.is_dir()):
        root_files_dir = parent_dir / "root_files"
        if root_files_dir.exists() and next(root_files_dir.iterdir(), None) is not None:
            plan.skipped_parents.append(parent_dir)
            continue
        job_dirs = sorted(
            p for p in parent_dir.iterdir()
            if p.is_dir() and p.name.startswith("job_")
        )
        for job_dir in job_dirs:
            root_files = list(job_dir.glob("*.root"))
            if not root_files:
                plan.empty_jobs.append(EmptyJob(parent_dir=parent_dir, job_dir=job_dir))
                continue
            for f in root_files:
                plan.moves.append(FileMove(
                    parent_dir=parent_dir,
                    job_dir=job_dir,
                    source=f,
                    dest=root_files_dir / f.name,
                    size=f.stat().st_size,
                ))
    return plan


def _format_size(size: int) -> str:
    s = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if s < 1024 or unit == "TB":
            return f"{s:.0f} {unit}"
        s /= 1024
    return f"{s:.0f} B"  # unreachable


def display_plan(plan: MovePlan, console: Console | None = None) -> None:
    if console is None:
        console = Console()

    for p in plan.skipped_parents:
        console.print(f"[yellow]SKIP[/yellow] {p.name}: root_files/ already non-empty")

    if not plan.moves and not plan.empty_jobs:
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("Parent Dir", style="dim")
    table.add_column("Job")
    table.add_column("File")
    table.add_column("Size", justify="right")
    table.add_column("Destination", style="dim")

    parent_names = sorted(
        {m.parent_dir.name for m in plan.moves}
        | {e.parent_dir.name for e in plan.empty_jobs}
    )
    colors = ["white", "bright_white"]
    color_map = {name: colors[i % 2] for i, name in enumerate(parent_names)}

    rows: list[FileMove | EmptyJob] = [*plan.moves, *plan.empty_jobs]
    rows.sort(key=lambda r: (
        r.parent_dir.name,
        r.job_dir.name,
        r.source.name if isinstance(r, FileMove) else "",
    ))

    for item in rows:
        if isinstance(item, FileMove):
            table.add_row(
                item.parent_dir.name,
                item.job_dir.name,
                item.source.name,
                _format_size(item.size),
                f"root_files/{item.source.name}",
                style=color_map[item.parent_dir.name],
            )
        else:
            table.add_row(
                item.parent_dir.name,
                item.job_dir.name,
                "[red]no .root files[/red]",
                "—",
                "—",
                style="red",
            )

    console.print(table)
    n_parents = len({m.parent_dir for m in plan.moves} | {e.parent_dir for e in plan.empty_jobs})
    n_jobs = len({m.job_dir for m in plan.moves} | {e.job_dir for e in plan.empty_jobs})
    console.print(
        f"[bold]{len(plan.moves)} files[/bold] across "
        f"{n_jobs} job dirs in {n_parents} parent dirs"
    )


def execute_plan(plan: MovePlan) -> int:
    parents: dict[Path, list[FileMove]] = {}
    for m in plan.moves:
        parents.setdefault(m.parent_dir, []).append(m)

    exit_code = 0
    for parent_dir, moves in sorted(parents.items()):
        dest_dir = parent_dir / "root_files"
        try:
            dest_dir.mkdir(exist_ok=True)
        except OSError as e:
            print(f"ERROR: {parent_dir.name}: cannot create root_files/: {e}", file=sys.stderr)
            exit_code = 1
            continue

        # track per-job success: only delete job dir if ALL its files moved
        job_failed: set[Path] = set()
        n_moved = 0
        for m in moves:
            try:
                shutil.move(m.source, m.dest)
                n_moved += 1
            except OSError as e:
                print(f"ERROR: {parent_dir.name}/{m.source.name}: {e}", file=sys.stderr)
                job_failed.add(m.job_dir)
                exit_code = 1

        job_dirs_all = {m.job_dir for m in moves}
        job_dirs_to_delete = job_dirs_all - job_failed
        for job_dir in job_dirs_to_delete:
            try:
                shutil.rmtree(job_dir)
            except OSError as e:
                print(f"ERROR: {parent_dir.name}/{job_dir.name}: {e}", file=sys.stderr)
                exit_code = 1

        print(f"{parent_dir.name}: moved {n_moved} files, deleted {len(job_dirs_to_delete)} job dirs")
    return exit_code


def main() -> int:
    cwd = Path.cwd()
    plan = scan_all(cwd)

    if not plan.moves and not plan.empty_jobs and not plan.skipped_parents:
        print("ERROR: no job_* directories found under any subdirectory", file=sys.stderr)
        return 1

    display_plan(plan)

    if not plan.moves:
        return 0

    answer = input("Proceed? [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return 0

    return execute_plan(plan)


if __name__ == "__main__":
    sys.exit(main())
