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
        fluka_parts = ["rfluka", "-M", "1"]
        if job_info.custom_exe is not None:
            fluka_parts.extend(["-e", job_info.custom_exe])
        fluka_parts.append(job_info.input_file)
        cmd_list = ["ts"] + fluka_parts

        if args.dry_run:
            cmd_str = " ".join(cmd_list)
            return f"[dry run] {cmd_str}"

        result = subprocess.run(cmd_list, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list[str]]:
        C = COLORS
        return [
            [" ", f"{C['B']}FLUKA bin{C['RE']}",    f"{C['B']}{fluka_path}{C['RE']}"],
            [" ", f"{C['B']}FLUKA folder{C['RE']}", f"{C['B']}{fluka_folder}{C['RE']}"],
        ]

    def set_priority_queue(self, args: Namespace, queue_name: str) -> None:
        # Task Spooler non ha concetto di coda/partizione; l'override viene ignorato.
        import logging as _logging
        _logging.warning("TSBackend: benchmark_priority_queue ignorato (nessun concetto di coda).")
