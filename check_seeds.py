#!/usr/bin/env python3
"""Audit job directories for duplicate FLUKA RANDOMIZ seeds."""

import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from core.fluka import parse_randomiz


def scan_seeds(root: Path) -> dict[int, list[Path]]:
    """Map each RANDOMIZ seed to the list of job .inp files using it."""
    seeds: dict[int, list[Path]] = {}
    for parent_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        job_dirs = sorted(
            p for p in parent_dir.iterdir()
            if p.is_dir() and p.name.startswith("job_")
        )
        for job_dir in job_dirs:
            for inp in sorted(job_dir.glob("*.inp")):
                seed = parse_randomiz(inp)
                if seed is None:
                    continue
                seeds.setdefault(seed, []).append(inp)
    return seeds


def has_duplicates(seeds: dict[int, list[Path]]) -> bool:
    return any(len(files) > 1 for files in seeds.values())


def display_report(seeds: dict[int, list[Path]], console: Console | None = None) -> None:
    if console is None:
        console = Console()

    n_files = sum(len(files) for files in seeds.values())

    if not seeds:
        console.print("[yellow]No job_* directories with parseable RANDOMIZ seeds found.[/yellow]")
        return

    if not has_duplicates(seeds):
        console.print(f"[green]{n_files} jobs, {len(seeds)} unique seeds — all unique.[/green]")
        return

    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
    table.add_column("Seed", justify="right", style="red")
    table.add_column("Count", justify="right")
    table.add_column("Job inputs", style="dim")

    for seed in sorted(s for s, files in seeds.items() if len(files) > 1):
        files = seeds[seed]
        table.add_row(
            str(seed),
            str(len(files)),
            ", ".join(str(f.parent.name) for f in files),
        )

    console.print(table)
    n_dup_seeds = sum(1 for files in seeds.values() if len(files) > 1)
    console.print(f"[bold red]{n_dup_seeds} duplicated seeds[/bold red] across {n_files} jobs")


def main() -> int:
    cwd = Path.cwd()
    seeds = scan_seeds(cwd)
    display_report(seeds)
    return 1 if has_duplicates(seeds) else 0


if __name__ == "__main__":
    sys.exit(main())
