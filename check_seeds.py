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
