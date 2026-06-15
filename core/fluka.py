import logging
import os
import random
import re
import subprocess
from pathlib import Path


def parse_randomiz(inp_path: Path) -> int | None:
    """Return the RANDOMIZ seed (WHAT(2)) from a FLUKA input, or None.

    Tolerant of fixed- and free-format spacing. The seed is the second
    numeric token on the RANDOMIZ line.
    """
    try:
        lines = Path(inp_path).read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        if "RANDOMIZ" not in line:
            continue
        rest = line.split("RANDOMIZ", 1)[1]
        numbers = re.findall(r"[-+]?\d*\.?\d+", rest)
        if len(numbers) < 2:
            return None
        return int(float(numbers[1]))
    return None


def allocate_seed(used: set[int]) -> int:
    """Draw a seed in [1, 9e7] not already in `used`; record and return it."""
    while True:
        seed = random.randint(1, int(9e7))
        if seed not in used:
            used.add(seed)
            return seed


def scan_existing_seeds(output_dir: Path) -> set[int]:
    """Return seeds already used by job_*/ inputs under output_dir."""
    root = Path(output_dir)
    seeds: set[int] = set()
    if not root.is_dir():
        return seeds
    for job_dir in root.glob("job_*"):
        if not job_dir.is_dir():
            continue
        for inp in job_dir.glob("*.inp"):
            seed = parse_randomiz(inp)
            if seed is not None:
                seeds.add(seed)
    return seeds


def detect_fluka_path() -> tuple[str, str]:
    try:
        bin_path = subprocess.check_output(["fluka-config", "--bin"]).decode().strip()
        folder_path = subprocess.check_output(["fluka-config", "--path"]).decode().strip()
        return bin_path, folder_path
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.error("FLUKA non trovato. Assicurati che fluka-config sia nel PATH.")
        raise SystemExit(1)


def generate_input(base_name: str, iteration: int, work_dir: str, nprim: int | None = None, seed: int | None = None) -> str:
    if seed is None:
        seed = random.randint(1, int(9e7))
    new_randomiz = f"RANDOMIZ          1.{seed:>10d}\n"

    src = os.path.join(work_dir, f"{base_name}.inp")
    with open(src, "r+") as f:
        data = f.readlines()
        for i, line in enumerate(data):
            if "RANDOMIZ" in line:
                data[i] = new_randomiz
                break
        else:
            raise ValueError(f"No RANDOMIZ card found in {src!r}")
        if nprim is not None:
            for i, line in enumerate(data):
                if line.startswith("START"):
                    data[i] = f"START   {nprim:>10d}.0\n"
                    break
            else:
                raise ValueError(f"No START card found in {src!r}")
        f.seek(0)
        f.writelines(data)
        f.truncate()

    filename = f"{base_name}_{iteration:04d}.inp"
    os.rename(src, os.path.join(work_dir, filename))
    return filename
