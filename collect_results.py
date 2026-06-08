#!/usr/bin/env python3
"""Collect ROOT files from FLUKA job subdirectories into root_files/."""

import argparse
import shutil
import sys
from pathlib import Path


def discover_sim_dirs(cwd: Path, pattern: str) -> list[Path]:
    return sorted(p for p in cwd.glob(pattern) if p.is_dir())
