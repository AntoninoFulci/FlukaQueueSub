#!/usr/bin/env python3
"""Collect ROOT files from FLUKA job subdirectories into root_files/."""

import argparse
import shutil
import sys
from pathlib import Path


def discover_sim_dirs(cwd: Path, pattern: str) -> list[Path]:
    return sorted(p for p in cwd.glob(pattern) if p.is_dir())


def collect_sim_dir(sim_dir: Path, dry_run: bool) -> tuple[int, int]:
    root_files_dir = sim_dir / "root_files"

    if root_files_dir.exists() and any(root_files_dir.iterdir()):
        print(f"WARNING: {sim_dir.name}: root_files/ already non-empty, skipping", file=sys.stderr)
        return 0, 0

    job_dirs = sorted(p for p in sim_dir.iterdir() if p.is_dir() and p.name.startswith("job_"))

    root_files = []
    for job_dir in job_dirs:
        job_roots = list(job_dir.glob("*.root"))
        if not job_roots:
            print(f"WARNING: {sim_dir.name}/{job_dir.name}: no .root files found", file=sys.stderr)
        root_files.extend(job_roots)

    if dry_run:
        for f in root_files:
            print(f"[DRY RUN] move {f} -> {root_files_dir / f.name}")
        for job_dir in job_dirs:
            print(f"[DRY RUN] delete {job_dir}")
        return len(root_files), len(job_dirs)

    root_files_dir.mkdir(exist_ok=True)
    for f in root_files:
        shutil.move(str(f), root_files_dir / f.name)
    for job_dir in job_dirs:
        shutil.rmtree(job_dir)

    print(f"{sim_dir.name}: moved {len(root_files)} root files, deleted {len(job_dirs)} job dirs")
    return len(root_files), len(job_dirs)
