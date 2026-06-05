import subprocess
from argparse import ArgumentParser, Namespace

from backends.base import JobInfo, QueueBackend
from core.display import COLORS


class TSBackend(QueueBackend):

    def add_args(self, parser: ArgumentParser) -> None:
        pass

    def validate(self, args: Namespace) -> None:
        pass

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> None:
        return None

    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        fluka_cmd = "rfluka -M 1"
        if job_info.custom_exe is not None:
            fluka_cmd += f" -e {job_info.custom_exe}"
        cmd = f"ts {fluka_cmd} {job_info.input_file}"

        if args.dry_run:
            return f"[dry run] {cmd}"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list[str]]:
        C = COLORS
        return [
            [" ", f"{C['B']}FLUKA bin{C['RE']}",    f"{C['B']}{fluka_path}{C['RE']}"],
            [" ", f"{C['B']}FLUKA folder{C['RE']}", f"{C['B']}{fluka_folder}{C['RE']}"],
        ]
