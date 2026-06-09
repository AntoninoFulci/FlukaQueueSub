import os
import subprocess
from argparse import ArgumentParser, Namespace
from string import Template

from backends.base import JobInfo, QueueBackend
from core.display import COLORS
from core.utils import parse_time_to_seconds

_DEFAULT_QUEUE = "production"
_MAX_TIME = "4-00:00:00"

_MAX_TIME_SECONDS = parse_time_to_seconds(_MAX_TIME)

_SCRIPT_TEMPLATE = Template("""\
#!/bin/bash

#SBATCH --job-name=$input
#SBATCH --nodes=$nodes
#SBATCH --mem=$mem
#SBATCH --ntasks=$ntasks
#SBATCH --time=$time
#SBATCH --gres=$gres
#SBATCH --output=/farm_out/%u/%x-%j-%N.out
#SBATCH --error=/farm_out/%u/%x-%j-%N.err

cd /scratch/slurm/$$SLURM_JOB_ID

# copia il .err di FLUKA ogni 30 secondi
while true; do
    cp fluka_*/*.err /farm_out/$$USER/$$SLURM_JOB_NAME-$$SLURM_JOB_ID-live.err 2>/dev/null
    sleep 30
done &
WATCHER_PID=$$!

echo
echo Launching FLUKA run...
$fluka_command $job_dir/$input

kill $$WATCHER_PID 2>/dev/null

echo
echo Job completed. Transferring files to $job_dir

mv ./*.root $job_dir
""")


class SlurmBackend(QueueBackend):

    def add_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("-q", "--queue", type=str, default=_DEFAULT_QUEUE,
                            help=f"Partizione SLURM su cui inviare i job (default: {_DEFAULT_QUEUE})")
        parser.add_argument("-m", "--mem", type=str, default="1500",
                            help="Memoria richiesta per nodo in MB (default: 1500)")
        parser.add_argument("-t", "--ntasks", type=int, default=1,
                            help="Numero di task SLURM per job, corrisponde a --ntasks (default: 1)")
        parser.add_argument("-o", "--nodes", type=int, default=1,
                            help="Numero di nodi richiesti per job, corrisponde a --nodes (default: 1)")
        parser.add_argument("-T", "--time", type=str, default="1-00:00:00",
                            help="Limite di tempo massimo nel formato D-HH:MM:SS, max 4-00:00:00 "
                                 "(default: 1-00:00:00)")
        parser.add_argument("-g", "--gres", type=str, default="disk:1G",
                            help="Risorse generiche SLURM (--gres), es. disk:2G o gpu:1 "
                                 "(default: disk:1G)")

    def validate(self, args: Namespace) -> None:
        if parse_time_to_seconds(args.time) > _MAX_TIME_SECONDS:
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
            gres=args.gres,
        )
        script_path = os.path.join(job_dir, f"job_{job_info.iteration:04d}.sh")
        with open(script_path, "w") as f:
            f.write(content)
        os.chmod(script_path, 0o755)
        return script_path

    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        if script_path is None:
            raise RuntimeError("SlurmBackend requires a script file (script_path cannot be None)")
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
            ["-g", f"{C['C']}GRES{C['RE']}",         f"{C['C']}{args.gres}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA bin{C['RE']}",   f"{C['B']}{fluka_path}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA folder{C['RE']}", f"{C['B']}{fluka_folder}{C['RE']}"],
        ]

    def set_priority_queue(self, args: Namespace, queue_name: str) -> None:
        args.queue = queue_name
