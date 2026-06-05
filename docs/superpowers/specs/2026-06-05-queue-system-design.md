# Design: Sistema unificato di lancio job FLUKA

**Data:** 2026-06-05
**Progetto:** FlukaQueueSub
**Branch:** main

---

## Obiettivo

Refactoring dei 4 script indipendenti (`launch_jobs_lsf.py`, `launch_jobs_slurm.py`, `launch_jobs_htcondor.py`, `launch_jobs_ts.py`) in un sistema coerente, estensibile e manutenibile. Il codice comune deve esistere una sola volta; ogni backend è isolato in un proprio modulo.

---

## Interfaccia utente

Un singolo entrypoint con subcommand per ogni queue system:

```
launch_jobs.py lsf    -f input.inp -n 10 --mem 1500 --time 1-00:00:00
launch_jobs.py slurm  -f input.inp -n 10 --mem 1500 --nodes 1 --time 1-00:00:00
launch_jobs.py condor -f input.inp -n 10 --mem 1500 --ncpu 1 --disk 100000
launch_jobs.py ts     -f input.inp -n 10
```

Gli argomenti comuni (`-f`, `-n`, `-c`, `-w`, `-d`) sono definiti nel parser principale. Gli argomenti specifici del backend sono aggiunti da ogni backend nel proprio subparser.

---

## Struttura dei file

```
launch_jobs.py              <- entrypoint: registra backend, costruisce parser, esegue loop
core/
  fluka.py                  <- generate_input(), detect_fluka_path()
  filesystem.py             <- setup_output_dir(), setup_job_dir()
  display.py                <- print_table(), confirm(), COLORS
backends/
  base.py                   <- classe astratta QueueBackend + dataclass JobInfo
  lsf.py                    <- LSFBackend
  slurm.py                  <- SlurmBackend
  htcondor.py               <- HTCondorBackend
  ts.py                     <- TSBackend
```

---

## Classe astratta `QueueBackend` (`backends/base.py`)

```python
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass

@dataclass
class JobInfo:
    input_file: str      # path al file .inp per questo job
    iteration: int       # indice del job (1-based)
    fluka_path: str      # path al binario rfluka
    custom_exe: str      # path all'exe custom, o "None"

class QueueBackend(ABC):

    @abstractmethod
    def add_args(self, parser: ArgumentParser) -> None:
        """Aggiunge gli argomenti specifici del backend al subparser."""

    @abstractmethod
    def validate(self, args: Namespace) -> None:
        """Valida gli argomenti. Lancia ValueError con messaggio leggibile se non validi."""

    @abstractmethod
    def generate_script(self, job_info: JobInfo, job_dir: str) -> str | None:
        """
        Genera il file .sh (o config) per il job nella directory job_dir.
        Restituisce il path del file generato, o None se il backend non usa script.
        """

    @abstractmethod
    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        """
        Invia il job. Restituisce una stringa descrittiva del risultato (job ID, ecc.).
        dry_run e' letto da args.dry_run.
        """

    @abstractmethod
    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list]:
        """Restituisce le righe specifiche del backend per la tabella di riepilogo."""
```

---

## Moduli `core/`

### `core/fluka.py`

| Funzione | Descrizione |
|---|---|
| `detect_fluka_path() -> tuple[str, str]` | Chiama `fluka-config --bin` e `--path`. Esce con errore se FLUKA non trovato. |
| `generate_input(base_name: str, iteration: int) -> str` | Randomizza il seed RANDOMIZ nel file `.inp`, rinomina in `{base}_{i:04d}.inp`, restituisce il nuovo nome. |

### `core/filesystem.py`

| Funzione | Descrizione |
|---|---|
| `setup_output_dir(base_name: str, output_dir: str \| None) -> str` | Crea la directory di output, aggiunge suffisso numerico se gia' esiste. Restituisce il path. |
| `setup_job_dir(output_dir: str, iteration: int, input_file: str) -> str` | Crea `{output_dir}/job_{i:04d}/`, copia il file `.inp`. Restituisce il path della job dir. |

### `core/display.py`

| Simbolo | Descrizione |
|---|---|
| `COLORS` | Dict con abbreviazioni: `G`, `R`, `Y`, `B`, `M`, `C`, `RE` (da colorama) |
| `print_table(rows: list[list]) -> None` | Stampa tabella con `tabulate` in formato `simple_outline`. |
| `confirm(prompt: str) -> bool` | Chiede conferma all'utente. Restituisce `True` se risponde yes/y. |

---

## Flusso dell'entrypoint (`launch_jobs.py`)

```
1. Registra i backend in un dict: {"lsf": LSFBackend(), "slurm": SlurmBackend(), ...}
2. Costruisce il parser principale con argomenti comuni
3. Aggiunge un subparser per ogni backend (chiama backend.add_args())
4. Parsea gli argomenti
5. Valida il file .inp (deve terminare con .inp)
6. Chiama detect_fluka_path()
7. Chiama backend.validate(args)
8. Costruisce la tabella: righe comuni + backend.table_rows()
9. Chiama print_table() e confirm()
10. Chiama setup_output_dir()
11. Per ogni job i in range(1, njobs+1):
    a. setup_job_dir(output_dir, i, input_file)
    b. os.chdir(job_dir)
    c. generate_input(base_name, i) -> new_input
    d. job_info = JobInfo(new_input, i, fluka_path, custom_exe)
    e. script_path = backend.generate_script(job_info, job_dir)
    f. result = backend.submit(script_path, job_info, args)
    g. print(f"Job {i}: {result}")
    h. os.chdir("../..")
```

---

## Differenze tra backend

| Backend | Script `.sh` | Comando di submit | Args specifici |
|---|---|---|---|
| LSF | Si (`#BSUB`) | `bsub < job.sh` | `--queue`, `--mem`, `--ntasks`, `--time` |
| Slurm | Si (`#SBATCH`) | `sbatch --partition=Q job.sh` | `--queue`, `--mem`, `--ntasks`, `--nodes`, `--time` |
| HTCondor | Si + submit dict | `htcondor.Schedd().submit()` | `--queue`, `--mem`, `--ncpu`, `--disk`, `--time`, `--transfer-files`, `--output`, `--error`, `--log` |
| Task Spooler | No | `ts rfluka -M 1 input.inp` | nessuno |

---

## Aggiungere un nuovo backend

1. Creare `backends/nuova_queue.py` con una classe che estende `QueueBackend`
2. Implementare i 5 metodi astratti
3. In `launch_jobs.py`, aggiungere una riga al dizionario di registrazione:

```python
BACKENDS = {
    "lsf":   LSFBackend(),
    "slurm": SlurmBackend(),
    "condor": HTCondorBackend(),
    "ts":    TSBackend(),
    "nuova": NuovaQueueBackend(),  # <- questa riga
}
```

Nessun altro file va modificato.

---

## Compatibilita'

I 4 script originali (`launch_jobs_lsf.py`, ecc.) vengono eliminati. Non e' richiesta compatibilita' con i vecchi nomi.

---

## Dipendenze

Invariate rispetto agli script originali:
- `colorama`
- `tabulate`
- `htcondor` (solo per HTCondor backend)
