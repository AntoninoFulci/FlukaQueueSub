import os
import shutil


def setup_output_dir(base_name: str, output_dir: str | None) -> str:
    base = base_name if output_dir is None else output_dir
    name = base
    counter = 1
    while os.path.exists(name):
        name = f"{base}_{counter}"
        counter += 1
    os.makedirs(name)
    return name


def setup_job_dir(output_dir: str, iteration: int, input_file: str) -> str:
    job_dir = os.path.join(output_dir, f"job_{iteration:04d}")
    os.makedirs(job_dir)
    shutil.copy(input_file, job_dir)
    return job_dir
