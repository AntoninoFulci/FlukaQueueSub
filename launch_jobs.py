#!/usr/bin/env python3

import logging
import os
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from typing import TypedDict

from backends.base import JobInfo, QueueBackend
from backends.htcondor import HTCondorBackend
from backends.lsf import LSFBackend
from backends.slurm import SlurmBackend
from backends.ts import TSBackend
from core import config, display, filesystem, fluka

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BACKENDS = {
    "lsf":    LSFBackend(),
    "slurm":  SlurmBackend(),
    "condor": HTCondorBackend(),
    "ts":     TSBackend(),
}

class _BenchmarkParams(TypedDict):
    njobs: int
    nprim: int
    use_priority_queue: bool


_BENCHMARK_MODES: dict[str, _BenchmarkParams] = {
    "quick":     {"njobs": 2,  "nprim": 100,  "use_priority_queue": True},
    "extensive": {"njobs": 5,  "nprim": 1000, "use_priority_queue": False},
}


def _apply_benchmark_overrides(args: Namespace, mode: str, backend: QueueBackend) -> None:
    if mode not in _BENCHMARK_MODES:
        raise ValueError(
            f"Modalita' benchmark sconosciuta: {mode!r}. Disponibili: {sorted(_BENCHMARK_MODES)}"
        )
    params = _BENCHMARK_MODES[mode]
    args.njobs = params["njobs"]
    args.nprim = params["nprim"]
    if params["use_priority_queue"]:
        queue_name = getattr(args, "benchmark_priority_queue", None)
        if not queue_name:
            raise ValueError(
                "Campo 'benchmark_priority_queue' richiesto per benchmark quick"
            )
        backend.set_priority_queue(args, queue_name)


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description=(
            "Lancia job FLUKA su diversi sistemi di code.\n"
            "\n"
            "Modalita' di utilizzo:\n"
            "\n"
            "  1) Subcomando diretto (CLI completo):\n"
            "       python launch_jobs.py <BACKEND> -f sim.inp -n 10 [opzioni]\n"
            "       python launch_jobs.py slurm -f sim.inp -n 5 -T 2-00:00:00\n"
            "       python launch_jobs.py condor -f sim.inp -n 20 -m 2000\n"
            "\n"
            "  2) File di configurazione YAML (singolo lancio):\n"
            "       python launch_jobs.py config.yaml\n"
            "       python launch_jobs.py JobConfigs/test_slurm.yaml\n"
            "\n"
            "  3) Cartella di file YAML (lancia tutti in sequenza):\n"
            "       python launch_jobs.py JobConfigs/\n"
            "\n"
            "  4) Modalita' benchmark (profili predefiniti):\n"
            "       python launch_jobs.py benchmark quick    config.yaml\n"
            "       python launch_jobs.py benchmark quick    JobConfigs/\n"
            "       python launch_jobs.py benchmark extensive config.yaml\n"
            "\n"
            "     quick:     2 job, 100 particelle, coda da benchmark_priority_queue\n"
            "     extensive: 5 job, 1000 particelle, coda invariata dal config\n"
            "\n"
            "Il file YAML deve contenere le stesse chiavi dei flag CLI.\n"
            "Esempio minimo (slurm):\n"
            "  backend: slurm\n"
            "  input: /path/to/sim.inp\n"
            "  njobs: 5\n"
            "  nprim: 10000        # opzionale\n"
            "  custom_exe: /path   # opzionale\n"
            "  benchmark_priority_queue: priority  # opzionale, richiesto per benchmark quick\n"
        ),
        formatter_class=RawTextHelpFormatter,
        epilog=(
            "Per la lista delle opzioni specifiche di ogni backend:\n"
            "  python launch_jobs.py slurm -h\n"
            "  python launch_jobs.py lsf -h\n"
            "  python launch_jobs.py condor -h\n"
            "  python launch_jobs.py ts -h\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="backend", metavar="BACKEND")
    subparsers.required = True

    for name, backend in BACKENDS.items():
        sub = subparsers.add_parser(name, help=f"Invia job a {name.upper()}")
        sub.add_argument("-f", "--input",      type=str, required=True,
                         help="Percorso al file di input FLUKA (deve terminare in .inp)")
        sub.add_argument("-n", "--njobs",      type=int, required=True,
                         help="Numero di job indipendenti da lanciare (uno per seed casuale)")
        sub.add_argument("-c", "--custom-exe", type=str, default=None,
                         dest="custom_exe",
                         help="Percorso all'eseguibile FLUKA custom (passato come -e a rfluka); "
                              "se omesso usa l'eseguibile di default di FLUKA")
        sub.add_argument("-w", "--dry-run",    action="store_true",
                         dest="dry_run",
                         help="Modalita' dry-run: costruisce gli script e mostra i comandi "
                              "senza inviare alcun job al sistema di code")
        sub.add_argument("-d", "--output-dir", type=str, default=None,
                         dest="output_dir",
                         help="Directory radice dove creare le sottocartelle dei job "
                              "(default: nome del file di input senza estensione)")
        sub.add_argument("-N", "--nprim", type=int, default=None,
                         dest="nprim",
                         help="Numero di particelle primarie per job: sovrascrive la card "
                              "START nel file .inp rispettando il formato colonnare FLUKA; "
                              "se omesso il valore nel .inp rimane invariato")
        backend.add_args(sub)

    return parser


def _execute_jobs(args: Namespace, fluka_path: str) -> None:
    backend = BACKENDS[args.backend]
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    output_dir = filesystem.setup_output_dir(base_name, args.output_dir)

    for i in range(1, args.njobs + 1):
        job_dir = filesystem.setup_job_dir(output_dir, i, args.input)
        new_input = fluka.generate_input(base_name, i, job_dir, nprim=args.nprim)
        job_info = JobInfo(new_input, i, fluka_path, args.custom_exe)
        script_path = backend.generate_script(job_info, job_dir, args)
        try:
            result = backend.submit(script_path, job_info, args)
            logging.info("Job %d: %s", i, result)
        except RuntimeError as e:
            logging.error("Job %d fallito: %s", i, e)


def run_from_args(args: Namespace) -> None:
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
    common_rows = [
        ["Flag", "Parametro", "Valore"],
        ["-f", f"{C['R']}Input file{C['RE']}",  f"{C['M']}{args.input}{C['RE']}"],
        ["-n", f"{C['R']}Numero job{C['RE']}",  f"{C['M']}{args.njobs}{C['RE']}"],
        ["-c", f"{C['M']}Custom exe{C['RE']}",  f"{C['M']}{args.custom_exe or 'None'}{C['RE']}"],
        ["-d", f"{C['B']}Output dir{C['RE']}",  f"{C['B']}{args.output_dir or 'Default'}{C['RE']}"],
        ["-N", f"{C['C']}N. primarie{C['RE']}", f"{C['C']}{args.nprim if args.nprim is not None else 'dal file'}{C['RE']}"],
        ["-w", f"{C['Y']}Dry run{C['RE']}",     f"{C['Y']}{args.dry_run}{C['RE']}"],
    ]
    display.print_table(common_rows + backend.table_rows(args, fluka_path, fluka_folder))

    if not display.confirm():
        logging.info("Lancio annullato.")
        sys.exit(0)

    _execute_jobs(args, fluka_path)


def run_folder(folder: str) -> None:
    yaml_files = sorted(
        f for f in os.listdir(folder) if f.endswith((".yaml", ".yml"))
    )
    yaml_paths = [os.path.join(folder, f) for f in yaml_files]

    if not yaml_paths:
        logging.warning("Nessun file YAML trovato in %r", folder)
        return

    configs = []
    for path in yaml_paths:
        try:
            cfg = config.load_yaml_config(path, BACKENDS)
            BACKENDS[cfg.backend].validate(cfg)
            configs.append((path, cfg))
        except Exception as e:
            logging.error("File %r non valido: %s", path, e)

    if not configs:
        logging.error("Nessuna configurazione valida trovata.")
        return

    C = display.COLORS
    rows = [["File", "Backend", "N. job"]]
    for path, cfg in configs:
        rows.append([
            os.path.basename(path),
            f"{C['M']}{cfg.backend}{C['RE']}",
            f"{C['M']}{cfg.njobs}{C['RE']}",
        ])
    display.print_table(rows)

    if not display.confirm(f"Procedere con {len(configs)} lanci? (yes/no): "):
        logging.info("Lancio annullato.")
        return

    fluka_path, _ = fluka.detect_fluka_path()
    failures = 0
    for path, cfg in configs:
        try:
            logging.info("Avvio: %s", os.path.basename(path))
            _execute_jobs(cfg, fluka_path)
        except Exception as e:
            logging.error("Errore in %r: %s", path, e)
            failures += 1
    if failures:
        sys.exit(1)


def _has_start_card(inp_path: str) -> bool:
    """Return True if the FLUKA input file contains a START card."""
    with open(inp_path) as f:
        return any(line.startswith("START") for line in f)


def run_benchmark(mode: str, target: str) -> None:
    C = display.COLORS

    if os.path.isdir(target):
        yaml_files = sorted(f for f in os.listdir(target) if f.endswith((".yaml", ".yml")))
        yaml_paths = [os.path.join(target, f) for f in yaml_files]

        if not yaml_paths:
            logging.warning("Nessun file YAML trovato in %r", target)
            return

        configs = []
        for path in yaml_paths:
            try:
                cfg = config.load_yaml_config(path, BACKENDS)
                BACKENDS[cfg.backend].validate(cfg)
                configs.append((path, cfg))
            except Exception as e:
                logging.error("File %r non valido: %s", path, e)

        if not configs:
            logging.error("Nessuna configurazione valida trovata.")
            return

        for path, cfg in configs:
            try:
                _apply_benchmark_overrides(cfg, mode, BACKENDS[cfg.backend])
            except ValueError as e:
                logging.error(str(e))
                sys.exit(1)

        params = _BENCHMARK_MODES[mode]
        print(
            f"\n[BENCHMARK MODE: {mode} — "
            f"njobs={params['njobs']}, nprim={params['nprim']}"
            + (", priority_queue override active" if params["use_priority_queue"] else "")
            + "]"
        )
        rows = [["File", "Backend", "N. job (benchmark)"]]
        for path, cfg in configs:
            rows.append([
                os.path.basename(path),
                f"{C['M']}{cfg.backend}{C['RE']}",
                f"{C['M']}{cfg.njobs}{C['RE']}",
            ])
        display.print_table(rows)

        if not display.confirm(f"Procedere con {len(configs)} lanci benchmark? (yes/no): "):
            logging.info("Lancio annullato.")
            return

        fluka_path, _ = fluka.detect_fluka_path()
        failures = 0
        for path, cfg in configs:
            try:
                logging.info("Avvio benchmark: %s", os.path.basename(path))
                if cfg.nprim is not None and not _has_start_card(cfg.input):
                    logging.warning(
                        "Nessuna card START in %r — nprim ignorato per questo lancio.", cfg.input
                    )
                    cfg.nprim = None
                _execute_jobs(cfg, fluka_path)
            except Exception as e:
                logging.error("Errore in %r: %s", path, e)
                failures += 1
        if failures:
            sys.exit(1)

    else:
        try:
            cfg = config.load_yaml_config(target, BACKENDS)
        except (FileNotFoundError, ValueError) as e:
            logging.error(str(e))
            sys.exit(1)

        backend = BACKENDS[cfg.backend]
        try:
            backend.validate(cfg)
            _apply_benchmark_overrides(cfg, mode, backend)
        except ValueError as e:
            logging.error(str(e))
            sys.exit(1)

        if cfg.nprim is not None and not _has_start_card(cfg.input):
            logging.warning(
                "Nessuna card START in %r — nprim ignorato per questo lancio.", cfg.input
            )
            cfg.nprim = None

        params = _BENCHMARK_MODES[mode]
        print(
            f"\n[BENCHMARK MODE: {mode} — "
            f"njobs={params['njobs']}, nprim={params['nprim']}"
            + (", priority_queue override active" if params["use_priority_queue"] else "")
            + "]"
        )
        if not display.confirm("Procedere con lancio benchmark? (yes/no): "):
            logging.info("Lancio annullato.")
            return
        fluka_path, _ = fluka.detect_fluka_path()
        _execute_jobs(cfg, fluka_path)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        if len(sys.argv) != 4:
            print("Utilizzo: launch_jobs.py benchmark <quick|extensive> <config.yaml|cartella/>")
            sys.exit(1)
        if sys.argv[2] not in _BENCHMARK_MODES:
            print(f"Modalita' sconosciuta: {sys.argv[2]!r}. Disponibili: {sorted(_BENCHMARK_MODES)}")
            sys.exit(1)
        run_benchmark(sys.argv[2], sys.argv[3])
        return
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg.endswith((".yaml", ".yml")) and not os.path.isdir(first_arg):
            try:
                args = config.load_yaml_config(first_arg, BACKENDS)
            except (FileNotFoundError, ValueError) as e:
                logging.error(str(e))
                sys.exit(1)
            run_from_args(args)
            return
        if os.path.isdir(first_arg):
            run_folder(first_arg)
            return
    parser = _build_parser()
    args = parser.parse_args()
    run_from_args(args)


if __name__ == "__main__":
    main()
