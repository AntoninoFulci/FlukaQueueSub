import logging
import os
import random
import subprocess


def detect_fluka_path() -> tuple[str, str]:
    try:
        bin_path = subprocess.check_output(["fluka-config", "--bin"]).decode().strip()
        folder_path = subprocess.check_output(["fluka-config", "--path"]).decode().strip()
        return bin_path, folder_path
    except subprocess.CalledProcessError:
        logging.error("FLUKA non trovato. Assicurati che fluka-config sia nel PATH.")
        raise SystemExit(1)


def generate_input(base_name: str, iteration: int, work_dir: str) -> str:
    seed = random.randint(1, int(9e7))
    new_randomiz = f"RANDOMIZ          1.{seed:>10n}\n"

    src = os.path.join(work_dir, f"{base_name}.inp")
    with open(src, "r+") as f:
        data = f.readlines()
        for i, line in enumerate(data):
            if "RANDOMIZ" in line:
                data[i] = new_randomiz
                break
        f.seek(0)
        f.writelines(data)
        f.truncate()

    filename = f"{base_name}_{iteration:04d}.inp"
    os.rename(src, os.path.join(work_dir, filename))
    return filename
