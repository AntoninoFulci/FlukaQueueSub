import os
import subprocess
from argparse import ArgumentParser, Namespace
from string import Template

from backends.base import JobInfo, QueueBackend
from core.display import COLORS

_DEFAULT_QUEUE = "production"
_MAX_TIME = "4-00:00:00"


def _time_to_seconds(t: str) -> int:
    days, rest = t.split("-")
    h, m, s = rest.split(":")
    return int(days) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)

_MAX_TIME_SECONDS = _time_to_seconds(_MAX_TIME)

_SCRIPT_TEMPLATE = Template("""\
#!/bin/bash

#SBATCH --job-name=$input
#SBATCH --nodes=$nodes
#SBATCH --mem=$mem
#SBATCH --ntasks=$ntasks
#SBATCH --time=$time
#SBATCH --output=/farm_out/%u/%x-%j-%N.out
#SBATCH --error=/farm_out/%u/%x-%j-%N.err

cd /scratch/slurm/$$SLURM_JOB_ID

echo
echo Launching FLUKA run...
$fluka_command $job_dir/$input

echo
echo Job completed. Transferring files to $job_dir

mv ./*.root $job_dir

echo
cat ./*.err
""")


class SlurmBackend(QueueBackend):

    def add_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("-q", "--queue", type=str, default=_DEFAULT_QUEUE)
        parser.add_argument("-m", "--mem", type=str, default="1500")
        parser.add_argument("-t", "--ntasks", type=int, default=1)
        parser.add_argument("-o", "--nodes", type=int, default=1)
        parser.add_argument("-T", "--time", type=str, default="1-00:00:00")

    def validate(self, args: Namespace) -> None:
        if _time_to_seconds(args.time) > _MAX_TIME_SECONDS:
            raise ValueError(f"Il time limit non puo' superare {_MAX_TIME}")

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str:
        fluka_cmd = f"{job_info.fluka_path}/rfluka -M 1"
        if job_info.custom_exe is not None:
            fluka_cmd += f" -e {job_info.custom_exe}"

        content = _SCRIPT_TEMPLATE.substitute(
            input=job_info.input_file,
            fluka_command=fluka_cmd,
            job_dir=job_dir,
            mem=args.mem,
            ntasks=args.ntasks,
            nodes=args.nodes,
            time=args.time,
        )
        script_path = os.path.join(job_dir, f"job_{job_info.iteration:04d}.sh")
        with open(script_path, "w") as f:
            f.write(content)
        os.chmod(script_path, 0o755)
        return script_path

    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        if args.dry_run:
            return f"[dry run] sbatch --partition={args.queue} {script_path}"
        result = subprocess.run(
            ["sbatch", f"--partition={args.queue}", script_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list[str]]:
        C = COLORS
        return [
            ["-q", f"{C['M']}Partizione{C['RE']}",  f"{C['M']}{args.queue}{C['RE']}"],
            ["-m", f"{C['C']}Memoria (MB){C['RE']}", f"{C['C']}{args.mem}{C['RE']}"],
            ["-t", f"{C['C']}N. task{C['RE']}",     f"{C['C']}{args.ntasks}{C['RE']}"],
            ["-o", f"{C['C']}N. nodi{C['RE']}",     f"{C['C']}{args.nodes}{C['RE']}"],
            ["-T", f"{C['C']}Time limit{C['RE']}",  f"{C['C']}{args.time}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA bin{C['RE']}",   f"{C['B']}{fluka_path}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA folder{C['RE']}", f"{C['B']}{fluka_folder}{C['RE']}"],
        ]
