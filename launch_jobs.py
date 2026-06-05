#!/usr/bin/env python3

import logging
import os
import sys
from argparse import ArgumentParser, RawTextHelpFormatter

from backends.base import JobInfo
from backends.htcondor import HTCondorBackend
from backends.lsf import LSFBackend
from backends.slurm import SlurmBackend
from backends.ts import TSBackend
from core import display, filesystem, fluka

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BACKENDS = {
    "lsf":    LSFBackend(),
    "slurm":  SlurmBackend(),
    "condor": HTCondorBackend(),
    "ts":     TSBackend(),
}


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Lancia job FLUKA su diversi sistemi di code.",
        formatter_class=RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="backend", metavar="BACKEND")
    subparsers.required = True

    for name, backend in BACKENDS.items():
        sub = subparsers.add_parser(name, help=f"Invia job a {name.upper()}")
        sub.add_argument("-f", "--input",      type=str, required=True,
                         help="File di input FLUKA (.inp)")
        sub.add_argument("-n", "--njobs",      type=int, required=True,
                         help="Numero di job da lanciare")
        sub.add_argument("-c", "--custom-exe", type=str, default=None,
                         dest="custom_exe",
                         help="Percorso all'eseguibile custom")
        sub.add_argument("-w", "--dry-run",    action="store_true",
                         dest="dry_run",
                         help="Dry run: mostra i comandi senza inviare i job")
        sub.add_argument("-d", "--output-dir", type=str, default=None,
                         dest="output_dir",
                         help="Directory di output (default: nome del file input)")
        backend.add_args(sub)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.input.endswith(".inp"):
        logging.error("Il file di input deve terminare con .inp")
        sys.exit(1)

    fluka_path, fluka_folder = fluka.detect_fluka_path()

    backend = BACKENDS[args.backend]
    try:
        backend.validate(args)
    except ValueError as e:
        logging.error(str(e))
        sys.exit(1)

    C = display.COLORS
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    common_rows = [
        ["Flag", "Parametro", "Valore"],
        ["-f", f"{C['R']}Input file{C['RE']}",  f"{C['M']}{args.input}{C['RE']}"],
        ["-n", f"{C['R']}Numero job{C['RE']}",  f"{C['M']}{args.njobs}{C['RE']}"],
        ["-c", f"{C['M']}Custom exe{C['RE']}",  f"{C['M']}{args.custom_exe or 'None'}{C['RE']}"],
        ["-d", f"{C['B']}Output dir{C['RE']}",  f"{C['B']}{args.output_dir or 'Default'}{C['RE']}"],
        ["-w", f"{C['Y']}Dry run{C['RE']}",     f"{C['Y']}{args.dry_run}{C['RE']}"],
    ]
    display.print_table(common_rows + backend.table_rows(args, fluka_path, fluka_folder))

    if not display.confirm():
        logging.info("Lancio annullato.")
        sys.exit(0)

    output_dir = filesystem.setup_output_dir(base_name, args.output_dir)

    for i in range(1, args.njobs + 1):
        job_dir = filesystem.setup_job_dir(output_dir, i, args.input)
        new_input = fluka.generate_input(base_name, i, job_dir)
        job_info = JobInfo(new_input, i, fluka_path, args.custom_exe)
        script_path = backend.generate_script(job_info, job_dir, args)
        try:
            result = backend.submit(script_path, job_info, args)
            print(f"Job {i}: {result}")
        except RuntimeError as e:
            logging.error(f"Job {i} fallito: {e}")


if __name__ == "__main__":
    main()
