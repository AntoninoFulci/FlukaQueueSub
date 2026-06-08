import os
from argparse import ArgumentParser, Namespace
from string import Template

from backends.base import JobInfo, QueueBackend
from core.display import COLORS

try:
    import htcondor
except ImportError:
    htcondor = None  # type: ignore

_MAX_TIME = 345600  # 4 giorni in secondi

_SCRIPT_TEMPLATE = Template("""\
#!/bin/env bash

. /cvmfs/sft.cern.ch/lcg/views/setupViews.sh LCG_97python3 x86_64-centos7-gcc9-opt

$fluka_command $input
""")


class HTCondorBackend(QueueBackend):

    def add_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("-q", "--queue", type=str, default="vanilla",
                            help="Universe HTCondor (default: vanilla)")
        parser.add_argument("-m", "--mem", type=str, default="1500",
                            help="Memoria richiesta in MB (request_memory, default: 1500)")
        parser.add_argument("-t", "--ncpu", type=int, default=1,
                            help="Numero di CPU richieste (request_cpus, default: 1)")
        parser.add_argument("-o", "--disk", type=int, default=100000,
                            help="Spazio disco richiesto in kB (request_disk, default: 100000)")
        parser.add_argument("-T", "--time", type=int, default=86400,
                            help="Tempo massimo di esecuzione in secondi (+MaxRuntime), "
                                 "max 345600 (4 giorni), default: 86400 (1 giorno)")
        parser.add_argument("--transfer-files", dest="transfer_files", type=str, default="yes",
                            help="Trasferisce i file di input al nodo worker "
                                 "(should_transfer_files: yes/no, default: yes)")
        parser.add_argument("--output", type=str, default="job_$(Cluster)_$(Process).out",
                            help="Pattern per il file di stdout del job "
                                 "(default: job_$(Cluster)_$(Process).out)")
        parser.add_argument("--error",  type=str, default="job_$(Cluster)_$(Process).err",
                            help="Pattern per il file di stderr del job "
                                 "(default: job_$(Cluster)_$(Process).err)")
        parser.add_argument("--log",    type=str, default="job_$(Cluster)_$(Process).log",
                            help="Pattern per il file di log HTCondor "
                                 "(default: job_$(Cluster)_$(Process).log)")

    def validate(self, args: Namespace) -> None:
        if args.time > _MAX_TIME:
            raise ValueError(f"Il time limit non puo' superare {_MAX_TIME} secondi")

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str:
        fluka_cmd = f"{job_info.fluka_path}/rfluka -M 1"
        if job_info.custom_exe is not None:
            fluka_cmd += f" -e {job_info.custom_exe}"

        content = _SCRIPT_TEMPLATE.substitute(
            fluka_command=fluka_cmd,
            input=job_info.input_file,
        )
        script_path = os.path.join(job_dir, f"job_{job_info.iteration:04d}.sh")
        with open(script_path, "w") as f:
            f.write(content)
        os.chmod(script_path, 0o755)
        return script_path

    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        submit_desc = {
            "universe": args.queue,
            "executable": script_path,
            "transfer_input_files": job_info.input_file,
            "should_transfer_files": args.transfer_files,
            "when_to_transfer_output": "ON_EXIT",
            "output": args.output,
            "error": args.error,
            "log": args.log,
            "request_memory": args.mem,
            "request_cpus": str(args.ncpu),
            "request_disk": str(args.disk),
            "+MaxRuntime": str(args.time),
        }
        if args.dry_run:
            return f"[dry run] condor_submit {submit_desc}"
        if htcondor is None:
            raise RuntimeError(
                "Il pacchetto htcondor non e' installato. Installarlo con: pip install htcondor"
            )

        schedd = htcondor.Schedd()
        result = schedd.submit(htcondor.Submit(submit_desc))
        return f"cluster {result.cluster()}"

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list[str]]:
        C = COLORS
        return [
            ["-q",               f"{C['M']}Universe{C['RE']}",       f"{C['M']}{args.queue}{C['RE']}"],
            ["-m",               f"{C['C']}Memoria (MB){C['RE']}",   f"{C['C']}{args.mem}{C['RE']}"],
            ["-t",               f"{C['C']}CPU{C['RE']}",            f"{C['C']}{args.ncpu}{C['RE']}"],
            ["-o",               f"{C['C']}Disco (kB){C['RE']}",     f"{C['C']}{args.disk}{C['RE']}"],
            ["-T",               f"{C['C']}Time limit (s){C['RE']}", f"{C['C']}{args.time}{C['RE']}"],
            [" ",                f"{C['B']}FLUKA bin{C['RE']}",      f"{C['B']}{fluka_path}{C['RE']}"],
            [" ",                f"{C['B']}FLUKA folder{C['RE']}",   f"{C['B']}{fluka_folder}{C['RE']}"],
            ["--transfer-files", f"{C['Y']}Transfer files{C['RE']}", f"{C['Y']}{args.transfer_files}{C['RE']}"],
            ["--output",         f"{C['Y']}Output file{C['RE']}",    f"{C['Y']}{args.output}{C['RE']}"],
            ["--error",          f"{C['Y']}Error file{C['RE']}",     f"{C['Y']}{args.error}{C['RE']}"],
            ["--log",            f"{C['Y']}Log file{C['RE']}",       f"{C['Y']}{args.log}{C['RE']}"],
        ]

    def set_priority_queue(self, args: Namespace, queue_name: str) -> None:
        # HTCondor usa 'universe', non una partizione/coda nominata; l'override viene ignorato.
        pass
