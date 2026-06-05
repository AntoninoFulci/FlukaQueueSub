# Queue System Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor 4 standalone FLUKA job-launching scripts into a single `launch_jobs.py` entrypoint with pluggable queue backends, a shared `core/` library, and an ABC-based extension point.

**Architecture:** A single entrypoint dispatches to a registered `QueueBackend` subclass selected by subcommand (`lsf`, `slurm`, `condor`, `ts`). Common logic (FLUKA detection, input file randomization, directory setup, display) lives in focused `core/` modules. Each backend lives in its own file under `backends/` and is responsible only for its script template and submission command.

**Tech Stack:** Python 3.10+, `colorama`, `tabulate`, `htcondor` (HTCondor only), `pytest`, `unittest.mock`

> **Nota spec:** `generate_script` riceve anche `args: Namespace` (non presente nella spec originale) perche' ha bisogno dei parametri specifici del backend (mem, time, ecc.). `generate_input` riceve `work_dir: str` per eliminare l'uso di `os.chdir` nel loop principale.

---

## File Map

| File | Azione | Responsabilita' |
|---|---|---|
| `backends/__init__.py` | Crea | Package marker |
| `backends/base.py` | Crea | `QueueBackend` ABC + `JobInfo` dataclass |
| `backends/lsf.py` | Crea | `LSFBackend` |
| `backends/slurm.py` | Crea | `SlurmBackend` |
| `backends/htcondor.py` | Crea | `HTCondorBackend` |
| `backends/ts.py` | Crea | `TSBackend` |
| `core/__init__.py` | Crea | Package marker |
| `core/fluka.py` | Crea | `detect_fluka_path()`, `generate_input()` |
| `core/filesystem.py` | Crea | `setup_output_dir()`, `setup_job_dir()` |
| `core/display.py` | Crea | `COLORS`, `print_table()`, `confirm()` |
| `launch_jobs.py` | Crea | Entrypoint: registra backend, costruisce parser, esegue loop |
| `tests/` | Crea | Test suite |
| `scripts/launch_jobs_lsf.py` | Elimina | Rimpiazzato |
| `scripts/launch_jobs_slurm.py` | Elimina | Rimpiazzato |
| `scripts/launch_jobs_htcondor.py` | Elimina | Rimpiazzato |
| `scripts/launch_jobs_ts.py` | Elimina | Rimpiazzato |

---

## Task 1: Scaffolding e `backends/base.py`

**Files:**
- Create: `backends/__init__.py`
- Create: `core/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/backends/__init__.py`
- Create: `tests/core/__init__.py`
- Create: `backends/base.py`
- Create: `tests/backends/test_base.py`

- [ ] **Step 1: Crea i package marker**

```bash
mkdir -p backends core tests/backends tests/core
touch backends/__init__.py core/__init__.py tests/__init__.py tests/backends/__init__.py tests/core/__init__.py
```

- [ ] **Step 2: Scrivi il test per la classe astratta**

`tests/backends/test_base.py`:
```python
import pytest
from argparse import ArgumentParser, Namespace
from backends.base import QueueBackend, JobInfo


class ConcreteBackend(QueueBackend):
    def add_args(self, parser): pass
    def validate(self, args): pass
    def generate_script(self, job_info, job_dir, args): return "/tmp/job.sh"
    def submit(self, script_path, job_info, args): return "submitted"
    def table_rows(self, args, fluka_path, fluka_folder): return []


def test_jobinfo_fields():
    ji = JobInfo(input_file="sim_0001.inp", iteration=1, fluka_path="/usr/bin", custom_exe="None")
    assert ji.input_file == "sim_0001.inp"
    assert ji.iteration == 1


def test_cannot_instantiate_abstract_backend():
    with pytest.raises(TypeError):
        QueueBackend()


def test_concrete_backend_instantiates():
    b = ConcreteBackend()
    assert b.submit(None, JobInfo("f", 1, "/p", "None"), Namespace()) == "submitted"
```

- [ ] **Step 3: Esegui il test per verificare che fallisce**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && python -m pytest tests/backends/test_base.py -v
```
Atteso: `ModuleNotFoundError` (il modulo non esiste ancora)

- [ ] **Step 4: Scrivi `backends/base.py`**

```python
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass


@dataclass
class JobInfo:
    input_file: str
    iteration: int
    fluka_path: str
    custom_exe: str


class QueueBackend(ABC):

    @abstractmethod
    def add_args(self, parser: ArgumentParser) -> None:
        """Aggiunge gli argomenti specifici del backend al subparser."""

    @abstractmethod
    def validate(self, args: Namespace) -> None:
        """Valida gli argomenti. Lancia ValueError se non validi."""

    @abstractmethod
    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str | None:
        """Genera lo script di job. Restituisce il path o None (es. Task Spooler)."""

    @abstractmethod
    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        """Invia il job. Restituisce una stringa descrittiva (job ID, ecc.)."""

    @abstractmethod
    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list]:
        """Restituisce le righe specifiche del backend per la tabella di riepilogo."""
```

- [ ] **Step 5: Esegui il test per verificare che passa**

```bash
python -m pytest tests/backends/test_base.py -v
```
Atteso: tutti i test PASS

- [ ] **Step 6: Commit**

```bash
git add backends/__init__.py backends/base.py core/__init__.py tests/__init__.py tests/backends/__init__.py tests/core/__init__.py tests/backends/test_base.py
git commit -m "feat: add QueueBackend ABC and JobInfo dataclass"
```

---

## Task 2: `core/fluka.py`

**Files:**
- Create: `core/fluka.py`
- Create: `tests/core/test_fluka.py`

- [ ] **Step 1: Scrivi i test**

`tests/core/test_fluka.py`:
```python
import os
import pytest
from unittest.mock import patch
from core.fluka import generate_input, detect_fluka_path


def test_generate_input_renames_file(tmp_path):
    base = "simulation"
    inp = tmp_path / f"{base}.inp"
    inp.write_text("TITLE test\nRANDOMIZ          1.  12345678\nSTOP\n")

    result = generate_input(base, 1, str(tmp_path))

    assert result == f"{base}_0001.inp"
    assert not (tmp_path / f"{base}.inp").exists()
    assert (tmp_path / result).exists()


def test_generate_input_updates_randomiz_seed(tmp_path):
    base = "simulation"
    inp = tmp_path / f"{base}.inp"
    inp.write_text("RANDOMIZ          1.  12345678\n")

    generate_input(base, 1, str(tmp_path))

    content = (tmp_path / f"{base}_0001.inp").read_text()
    assert "RANDOMIZ" in content
    assert "12345678" not in content


def test_generate_input_zero_pads_iteration(tmp_path):
    base = "sim"
    (tmp_path / f"{base}.inp").write_text("RANDOMIZ          1.  99999999\n")
    result = generate_input(base, 42, str(tmp_path))
    assert result == "sim_0042.inp"


def test_detect_fluka_path_returns_paths():
    with patch("subprocess.check_output", side_effect=[b"/usr/local/bin\n", b"/usr/local/fluka\n"]):
        bin_path, folder_path = detect_fluka_path()
    assert bin_path == "/usr/local/bin"
    assert folder_path == "/usr/local/fluka"


def test_detect_fluka_path_exits_if_not_found():
    import subprocess
    with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "fluka-config")):
        with pytest.raises(SystemExit):
            detect_fluka_path()
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/core/test_fluka.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `core/fluka.py`**

```python
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
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/core/test_fluka.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add core/fluka.py tests/core/test_fluka.py
git commit -m "feat: add core/fluka.py with generate_input and detect_fluka_path"
```

---

## Task 3: `core/filesystem.py`

**Files:**
- Create: `core/filesystem.py`
- Create: `tests/core/test_filesystem.py`

- [ ] **Step 1: Scrivi i test**

`tests/core/test_filesystem.py`:
```python
import os
import pytest
from core.filesystem import setup_output_dir, setup_job_dir


def test_setup_output_dir_creates_directory(tmp_path):
    os.chdir(tmp_path)
    result = setup_output_dir("myrun", None)
    assert result == "myrun"
    assert os.path.isdir(result)


def test_setup_output_dir_uses_custom_name(tmp_path):
    os.chdir(tmp_path)
    result = setup_output_dir("myrun", "custom_output")
    assert result == "custom_output"
    assert os.path.isdir(result)


def test_setup_output_dir_avoids_collision(tmp_path):
    os.chdir(tmp_path)
    setup_output_dir("myrun", None)
    result = setup_output_dir("myrun", None)
    assert result == "myrun_1"
    assert os.path.isdir(result)


def test_setup_output_dir_multiple_collisions(tmp_path):
    os.chdir(tmp_path)
    setup_output_dir("run", None)
    setup_output_dir("run", None)
    result = setup_output_dir("run", None)
    assert result == "run_2"


def test_setup_job_dir_creates_subdirectory(tmp_path):
    output_dir = str(tmp_path / "output")
    os.makedirs(output_dir)
    inp = tmp_path / "sim.inp"
    inp.write_text("content")

    job_dir = setup_job_dir(output_dir, 1, str(inp))

    assert os.path.isdir(job_dir)
    assert os.path.basename(job_dir) == "job_0001"
    assert os.path.isfile(os.path.join(job_dir, "sim.inp"))


def test_setup_job_dir_zero_pads_iteration(tmp_path):
    output_dir = str(tmp_path / "output")
    os.makedirs(output_dir)
    inp = tmp_path / "sim.inp"
    inp.write_text("x")

    job_dir = setup_job_dir(output_dir, 7, str(inp))
    assert os.path.basename(job_dir) == "job_0007"
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/core/test_filesystem.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `core/filesystem.py`**

```python
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
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/core/test_filesystem.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add core/filesystem.py tests/core/test_filesystem.py
git commit -m "feat: add core/filesystem.py with setup_output_dir and setup_job_dir"
```

---

## Task 4: `core/display.py`

**Files:**
- Create: `core/display.py`
- Create: `tests/core/test_display.py`

- [ ] **Step 1: Scrivi i test**

`tests/core/test_display.py`:
```python
from unittest.mock import patch
from core.display import confirm, COLORS, print_table


def test_confirm_returns_true_on_yes():
    with patch("builtins.input", return_value="yes"):
        assert confirm() is True


def test_confirm_returns_true_on_y():
    with patch("builtins.input", return_value="y"):
        assert confirm() is True


def test_confirm_returns_false_on_no():
    with patch("builtins.input", return_value="no"):
        assert confirm() is False


def test_confirm_returns_false_on_other():
    with patch("builtins.input", return_value="maybe"):
        assert confirm() is False


def test_colors_dict_has_expected_keys():
    for key in ("G", "R", "Y", "B", "M", "C", "RE"):
        assert key in COLORS


def test_print_table_runs_without_error(capsys):
    rows = [["Command", "Parameter", "Value"], ["-f", "Input", "sim.inp"]]
    print_table(rows)
    out = capsys.readouterr().out
    assert "Input" in out
    assert "sim.inp" in out
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/core/test_display.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `core/display.py`**

```python
from colorama import Fore, Style, init
from tabulate import tabulate

init(autoreset=True)

COLORS = {
    "G":  Fore.GREEN,
    "R":  Fore.RED,
    "Y":  Fore.YELLOW,
    "B":  Fore.BLUE,
    "M":  Fore.MAGENTA,
    "C":  Fore.CYAN,
    "RE": Style.RESET_ALL,
}


def print_table(rows: list[list]) -> None:
    print(tabulate(rows, headers="firstrow", tablefmt="simple_outline"))


def confirm(prompt: str = "Procedere con il lancio dei job? (yes/no): ") -> bool:
    return input(prompt).lower() in ("yes", "y")
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/core/test_display.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add core/display.py tests/core/test_display.py
git commit -m "feat: add core/display.py with COLORS, print_table, confirm"
```

---

## Task 5: `backends/lsf.py`

**Files:**
- Create: `backends/lsf.py`
- Create: `tests/backends/test_lsf.py`

- [ ] **Step 1: Scrivi i test**

`tests/backends/test_lsf.py`:
```python
import os
import pytest
from argparse import Namespace
from unittest.mock import patch
from backends.lsf import LSFBackend
from backends.base import JobInfo


BACKEND = LSFBackend()


def make_args(**kwargs):
    defaults = dict(queue="normal", mem="1500", ntasks=1, time="1-00:00:00", dry_run=False, custom_exe="None")
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_validate_accepts_valid_time():
    BACKEND.validate(make_args(time="1-00:00:00"))


def test_validate_rejects_time_over_max():
    with pytest.raises(ValueError, match="4-00:00:00"):
        BACKEND.validate(make_args(time="5-00:00:00"))


def test_generate_script_creates_sh_file(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    script = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert script.endswith("job_0001.sh")
    assert os.path.isfile(script)


def test_generate_script_contains_bsub_directives(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    args = make_args(queue="myqueue", mem="2000", ntasks=2, time="2-00:00:00")
    content = open(BACKEND.generate_script(job_info, str(tmp_path), args)).read()
    assert "#BSUB" in content
    assert "myqueue" in content
    assert "2000" in content
    assert "rfluka -M 1" in content


def test_generate_script_includes_custom_exe(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "/path/to/myexe")
    content = open(BACKEND.generate_script(job_info, str(tmp_path), make_args())).read()
    assert "-e /path/to/myexe" in content


def test_submit_dry_run_returns_string():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    result = BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=True))
    assert "dry run" in result.lower()
    assert "bsub" in result


def test_submit_calls_bsub():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Job <12345> is submitted"
        result = BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=False))
    assert "12345" in result
    assert "bsub" in mock_run.call_args[0][0]


def test_submit_raises_on_failure():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Queue not found"
        with pytest.raises(RuntimeError, match="Queue not found"):
            BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=False))


def test_table_rows_returns_list():
    rows = BACKEND.table_rows(make_args(), "/bin", "/fluka")
    assert isinstance(rows, list)
    assert len(rows) > 0
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/backends/test_lsf.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `backends/lsf.py`**

```python
import os
import subprocess
from argparse import ArgumentParser, Namespace
from string import Template

from backends.base import JobInfo, QueueBackend
from core.display import COLORS

_DEFAULT_QUEUE = "normal"
_MAX_TIME = "4-00:00:00"

_SCRIPT_TEMPLATE = Template("""\
#!/bin/bash

#BSUB -J $input
#BSUB -n $ntasks
#BSUB -R "select[mem>$mem]rusage[mem=$mem]"
#BSUB -W $time
#BSUB -o $job_dir/%J.out
#BSUB -e $job_dir/%J.err
#BSUB -q $queue

cd $job_dir

echo
echo Launching FLUKA run...
$fluka_command $job_dir/$input
""")


class LSFBackend(QueueBackend):

    def add_args(self, parser: ArgumentParser) -> None:
        parser.add_argument("-q", "--queue", type=str, default=_DEFAULT_QUEUE,
                            help="Queue LSF (default: normal)")
        parser.add_argument("-m", "--mem", type=str, default="1500",
                            help="Memoria in MB (default: 1500)")
        parser.add_argument("-t", "--ntasks", type=int, default=1,
                            help="Numero di task per job (default: 1)")
        parser.add_argument("-T", "--time", type=str, default="1-00:00:00",
                            help="Limite di tempo (default: 1-00:00:00, max: 4-00:00:00)")

    def validate(self, args: Namespace) -> None:
        if args.time > _MAX_TIME:
            raise ValueError(f"Il time limit non puo' superare {_MAX_TIME}")

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str:
        fluka_cmd = f"{job_info.fluka_path}/rfluka -M 1"
        if job_info.custom_exe != "None":
            fluka_cmd += f" -e {job_info.custom_exe}"

        content = _SCRIPT_TEMPLATE.substitute(
            input=job_info.input_file,
            fluka_command=fluka_cmd,
            job_dir=job_dir,
            mem=args.mem,
            ntasks=args.ntasks,
            time=args.time,
            queue=args.queue,
        )
        script_path = os.path.join(job_dir, f"job_{job_info.iteration:04d}.sh")
        with open(script_path, "w") as f:
            f.write(content)
        os.chmod(script_path, 0o755)
        return script_path

    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        if args.dry_run:
            return f"[dry run] bsub < {script_path}"
        result = subprocess.run(f"bsub < {script_path}", shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list]:
        C = COLORS
        return [
            ["-q", f"{C['M']}Queue{C['RE']}",         f"{C['M']}{args.queue}{C['RE']}"],
            ["-m", f"{C['C']}Memoria (MB){C['RE']}",  f"{C['C']}{args.mem}{C['RE']}"],
            ["-t", f"{C['C']}N. task{C['RE']}",       f"{C['C']}{args.ntasks}{C['RE']}"],
            ["-T", f"{C['C']}Time limit{C['RE']}",    f"{C['C']}{args.time}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA bin{C['RE']}",     f"{C['B']}{fluka_path}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA folder{C['RE']}",  f"{C['B']}{fluka_folder}{C['RE']}"],
        ]
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/backends/test_lsf.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add backends/lsf.py tests/backends/test_lsf.py
git commit -m "feat: add LSFBackend"
```

---

## Task 6: `backends/slurm.py`

**Files:**
- Create: `backends/slurm.py`
- Create: `tests/backends/test_slurm.py`

- [ ] **Step 1: Scrivi i test**

`tests/backends/test_slurm.py`:
```python
import os
import pytest
from argparse import Namespace
from unittest.mock import patch
from backends.slurm import SlurmBackend
from backends.base import JobInfo


BACKEND = SlurmBackend()


def make_args(**kwargs):
    defaults = dict(queue="production", mem="1500", ntasks=1, nodes=1,
                    time="1-00:00:00", dry_run=False, custom_exe="None")
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_validate_accepts_valid_time():
    BACKEND.validate(make_args(time="2-00:00:00"))


def test_validate_rejects_time_over_max():
    with pytest.raises(ValueError):
        BACKEND.validate(make_args(time="5-00:00:00"))


def test_generate_script_creates_sh_file(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    script = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert os.path.isfile(script)
    assert script.endswith("job_0001.sh")


def test_generate_script_contains_sbatch_directives(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    args = make_args(mem="3000", ntasks=4, nodes=2)
    content = open(BACKEND.generate_script(job_info, str(tmp_path), args)).read()
    assert "#SBATCH" in content
    assert "3000" in content


def test_submit_dry_run(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    result = BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=True, queue="mypartition"))
    assert "dry run" in result.lower()
    assert "sbatch" in result
    assert "mypartition" in result


def test_submit_calls_sbatch():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Submitted batch job 99"
        result = BACKEND.submit("/tmp/job.sh", job_info, make_args(dry_run=False, queue="prod"))
    assert "99" in result
    assert "sbatch" in mock_run.call_args[0][0]
    assert "prod" in mock_run.call_args[0][0]


def test_submit_raises_on_failure():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Partition not found"
        with pytest.raises(RuntimeError, match="Partition not found"):
            BACKEND.submit("/tmp/job.sh", job_info, make_args(dry_run=False))
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/backends/test_slurm.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `backends/slurm.py`**

```python
import os
import subprocess
from argparse import ArgumentParser, Namespace
from string import Template

from backends.base import JobInfo, QueueBackend
from core.display import COLORS

_DEFAULT_QUEUE = "production"
_MAX_TIME = "4-00:00:00"

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
        parser.add_argument("-q", "--queue", type=str, default=_DEFAULT_QUEUE,
                            help="Partizione Slurm (default: production)")
        parser.add_argument("-m", "--mem", type=str, default="1500",
                            help="Memoria in MB (default: 1500)")
        parser.add_argument("-t", "--ntasks", type=int, default=1,
                            help="Numero di task per job (default: 1)")
        parser.add_argument("-o", "--nodes", type=int, default=1,
                            help="Numero di nodi (default: 1)")
        parser.add_argument("-T", "--time", type=str, default="1-00:00:00",
                            help="Limite di tempo (default: 1-00:00:00, max: 4-00:00:00)")

    def validate(self, args: Namespace) -> None:
        if args.time > _MAX_TIME:
            raise ValueError(f"Il time limit non puo' superare {_MAX_TIME}")

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str:
        fluka_cmd = f"{job_info.fluka_path}/rfluka -M 1"
        if job_info.custom_exe != "None":
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
            f"sbatch --partition={args.queue} {script_path}",
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list]:
        C = COLORS
        return [
            ["-q", f"{C['M']}Partizione{C['RE']}",   f"{C['M']}{args.queue}{C['RE']}"],
            ["-m", f"{C['C']}Memoria (MB){C['RE']}", f"{C['C']}{args.mem}{C['RE']}"],
            ["-t", f"{C['C']}N. task{C['RE']}",      f"{C['C']}{args.ntasks}{C['RE']}"],
            ["-o", f"{C['C']}N. nodi{C['RE']}",      f"{C['C']}{args.nodes}{C['RE']}"],
            ["-T", f"{C['C']}Time limit{C['RE']}",   f"{C['C']}{args.time}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA bin{C['RE']}",    f"{C['B']}{fluka_path}{C['RE']}"],
            [" ",  f"{C['B']}FLUKA folder{C['RE']}", f"{C['B']}{fluka_folder}{C['RE']}"],
        ]
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/backends/test_slurm.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add backends/slurm.py tests/backends/test_slurm.py
git commit -m "feat: add SlurmBackend"
```

---

## Task 7: `backends/ts.py`

**Files:**
- Create: `backends/ts.py`
- Create: `tests/backends/test_ts.py`

- [ ] **Step 1: Scrivi i test**

`tests/backends/test_ts.py`:
```python
import pytest
from argparse import Namespace
from unittest.mock import patch
from backends.ts import TSBackend
from backends.base import JobInfo


BACKEND = TSBackend()


def make_args(**kwargs):
    defaults = dict(dry_run=False, custom_exe="None")
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_validate_does_not_raise():
    BACKEND.validate(make_args())


def test_generate_script_returns_none(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    result = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert result is None


def test_submit_dry_run_contains_ts_and_rfluka():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    result = BACKEND.submit(None, job_info, make_args(dry_run=True))
    assert "dry run" in result.lower()
    assert "ts" in result
    assert "rfluka" in result
    assert "sim_0001.inp" in result


def test_submit_dry_run_with_custom_exe():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "/path/to/exe")
    result = BACKEND.submit(None, job_info, make_args(dry_run=True, custom_exe="/path/to/exe"))
    assert "-e /path/to/exe" in result


def test_submit_calls_ts():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "3"
        result = BACKEND.submit(None, job_info, make_args(dry_run=False))
    assert "3" in result
    assert mock_run.call_args[0][0].startswith("ts ")
    assert "rfluka" in mock_run.call_args[0][0]


def test_submit_raises_on_failure():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "ts: command not found"
        with pytest.raises(RuntimeError, match="ts: command not found"):
            BACKEND.submit(None, job_info, make_args(dry_run=False))


def test_table_rows_returns_list():
    rows = BACKEND.table_rows(make_args(), "/bin", "/fluka")
    assert isinstance(rows, list)
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/backends/test_ts.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `backends/ts.py`**

```python
import subprocess
from argparse import ArgumentParser, Namespace

from backends.base import JobInfo, QueueBackend
from core.display import COLORS


class TSBackend(QueueBackend):

    def add_args(self, parser: ArgumentParser) -> None:
        pass  # Task Spooler non ha argomenti specifici

    def validate(self, args: Namespace) -> None:
        pass

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> None:
        return None  # TS non usa script shell

    def submit(self, script_path: str | None, job_info: JobInfo, args: Namespace) -> str:
        fluka_cmd = "rfluka -M 1"
        if job_info.custom_exe != "None":
            fluka_cmd += f" -e {job_info.custom_exe}"
        cmd = f"ts {fluka_cmd} {job_info.input_file}"

        if args.dry_run:
            return f"[dry run] {cmd}"

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list]:
        C = COLORS
        return [
            [" ", f"{C['B']}FLUKA bin{C['RE']}",    f"{C['B']}{fluka_path}{C['RE']}"],
            [" ", f"{C['B']}FLUKA folder{C['RE']}", f"{C['B']}{fluka_folder}{C['RE']}"],
        ]
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/backends/test_ts.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add backends/ts.py tests/backends/test_ts.py
git commit -m "feat: add TSBackend (Task Spooler)"
```

---

## Task 8: `backends/htcondor.py`

**Files:**
- Create: `backends/htcondor.py`
- Create: `tests/backends/test_htcondor.py`

- [ ] **Step 1: Scrivi i test**

`tests/backends/test_htcondor.py`:
```python
import os
import pytest
from argparse import Namespace
from unittest.mock import patch, MagicMock
from backends.htcondor import HTCondorBackend
from backends.base import JobInfo


BACKEND = HTCondorBackend()


def make_args(**kwargs):
    defaults = dict(
        queue="vanilla", mem="1500", ncpu=1, disk=100000,
        time=86400, dry_run=False, custom_exe="None",
        transfer_files="yes",
        output="job_$(Cluster)_$(Process).out",
        error="job_$(Cluster)_$(Process).err",
        log="job_$(Cluster)_$(Process).log",
    )
    defaults.update(kwargs)
    return Namespace(**defaults)


def test_validate_accepts_valid_time():
    BACKEND.validate(make_args(time=86400))


def test_validate_rejects_time_over_max():
    with pytest.raises(ValueError, match="345600"):
        BACKEND.validate(make_args(time=999999))


def test_generate_script_creates_sh_file(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    script = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert os.path.isfile(script)
    assert script.endswith("job_0001.sh")


def test_generate_script_contains_rfluka(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    content = open(BACKEND.generate_script(job_info, str(tmp_path), make_args())).read()
    assert "rfluka" in content


def test_submit_dry_run_returns_description():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    result = BACKEND.submit("/tmp/job.sh", job_info, make_args(dry_run=True))
    assert "dry run" in result.lower()
    assert "condor" in result.lower()


def test_submit_calls_schedd(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", "None")
    script = str(tmp_path / "job_0001.sh")
    open(script, "w").close()

    mock_submit_result = MagicMock()
    mock_submit_result.cluster.return_value = 42
    mock_schedd = MagicMock()
    mock_schedd.submit.return_value = mock_submit_result

    with patch("backends.htcondor.htcondor") as mock_htcondor:
        mock_htcondor.Schedd.return_value = mock_schedd
        mock_htcondor.Submit = dict
        result = BACKEND.submit(script, job_info, make_args(dry_run=False))

    assert "42" in result
    mock_schedd.submit.assert_called_once()


def test_table_rows_returns_list():
    rows = BACKEND.table_rows(make_args(), "/bin", "/fluka")
    assert isinstance(rows, list)
    assert len(rows) > 0
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/backends/test_htcondor.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `backends/htcondor.py`**

```python
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
                            help="Memoria richiesta in MB (default: 1500)")
        parser.add_argument("-t", "--ncpu", type=int, default=1,
                            help="CPU richieste per job (default: 1)")
        parser.add_argument("-o", "--disk", type=int, default=100000,
                            help="Disco richiesto in kB (default: 100000)")
        parser.add_argument("-T", "--time", type=int, default=86400,
                            help="Limite di tempo in secondi (default: 86400, max: 345600)")
        parser.add_argument("--transfer-files", dest="transfer_files", type=str, default="yes",
                            help="Trasferisci file (default: yes)")
        parser.add_argument("--output", type=str, default="job_$(Cluster)_$(Process).out")
        parser.add_argument("--error",  type=str, default="job_$(Cluster)_$(Process).err")
        parser.add_argument("--log",    type=str, default="job_$(Cluster)_$(Process).log")

    def validate(self, args: Namespace) -> None:
        if args.time > _MAX_TIME:
            raise ValueError(f"Il time limit non puo' superare {_MAX_TIME} secondi")

    def generate_script(self, job_info: JobInfo, job_dir: str, args: Namespace) -> str:
        fluka_cmd = f"{job_info.fluka_path}/rfluka -M 1"
        if job_info.custom_exe != "None":
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
            "universe": "vanilla",
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

        schedd = htcondor.Schedd()
        result = schedd.submit(htcondor.Submit(submit_desc))
        return f"cluster {result.cluster()}"

    def table_rows(self, args: Namespace, fluka_path: str, fluka_folder: str) -> list[list]:
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
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/backends/test_htcondor.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add backends/htcondor.py tests/backends/test_htcondor.py
git commit -m "feat: add HTCondorBackend"
```

---

## Task 9: `launch_jobs.py` (entrypoint)

**Files:**
- Create: `launch_jobs.py`
- Create: `tests/test_launch_jobs.py`

- [ ] **Step 1: Scrivi i test**

`tests/test_launch_jobs.py`:
```python
import os
import sys
import pytest
from unittest.mock import patch


def reload_and_run(argv):
    sys.argv = ["launch_jobs.py"] + argv
    import importlib
    import launch_jobs
    importlib.reload(launch_jobs)
    launch_jobs.main()


def test_no_subcommand_exits(capsys):
    sys.argv = ["launch_jobs.py"]
    import launch_jobs
    with pytest.raises(SystemExit):
        launch_jobs.main()


def test_invalid_extension_exits():
    sys.argv = ["launch_jobs.py", "ts", "-f", "input.txt", "-n", "1"]
    import launch_jobs
    with pytest.raises(SystemExit):
        launch_jobs.main()


def test_ts_dry_run_creates_job_dirs(tmp_path):
    inp = tmp_path / "myinput.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    sys.argv = ["launch_jobs.py", "ts", "-f", str(inp), "-n", "3", "-w"]
    os.chdir(tmp_path)

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import importlib, launch_jobs
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dir = tmp_path / "myinput"
    assert output_dir.is_dir()
    assert len(list(output_dir.iterdir())) == 3


def test_lsf_dry_run_creates_sh_files(tmp_path):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    sys.argv = ["launch_jobs.py", "lsf", "-f", str(inp), "-n", "2", "-w"]
    os.chdir(tmp_path)

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import importlib, launch_jobs
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dir = tmp_path / "sim"
    sh_files = list(output_dir.rglob("*.sh"))
    assert len(sh_files) == 2
```

- [ ] **Step 2: Esegui i test per verificare che falliscono**

```bash
python -m pytest tests/test_launch_jobs.py -v
```
Atteso: `ModuleNotFoundError`

- [ ] **Step 3: Scrivi `launch_jobs.py`**

```python
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
        sub.add_argument("-f", "--input",       type=str, required=True,
                         help="File di input FLUKA (.inp)")
        sub.add_argument("-n", "--njobs",       type=int, required=True,
                         help="Numero di job da lanciare")
        sub.add_argument("-c", "--custom-exe",  type=str, default="None",
                         dest="custom_exe",
                         help="Percorso all'eseguibile custom")
        sub.add_argument("-w", "--dry-run",     action="store_true",
                         dest="dry_run",
                         help="Dry run: mostra i comandi senza inviare i job")
        sub.add_argument("-d", "--output-dir",  type=str, default=None,
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
        ["-f", f"{C['R']}Input file{C['RE']}",   f"{C['M']}{args.input}{C['RE']}"],
        ["-n", f"{C['R']}Numero job{C['RE']}",   f"{C['M']}{args.njobs}{C['RE']}"],
        ["-c", f"{C['M']}Custom exe{C['RE']}",   f"{C['M']}{args.custom_exe}{C['RE']}"],
        ["-d", f"{C['B']}Output dir{C['RE']}",   f"{C['B']}{args.output_dir or 'Default'}{C['RE']}"],
        ["-w", f"{C['Y']}Dry run{C['RE']}",      f"{C['Y']}{args.dry_run}{C['RE']}"],
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
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest tests/test_launch_jobs.py -v
```
Atteso: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add launch_jobs.py tests/test_launch_jobs.py
git commit -m "feat: add launch_jobs.py entrypoint with subcommand dispatch"
```

---

## Task 10: Elimina i vecchi script e test finale

**Files:**
- Delete: `scripts/launch_jobs_lsf.py`
- Delete: `scripts/launch_jobs_slurm.py`
- Delete: `scripts/launch_jobs_htcondor.py`
- Delete: `scripts/launch_jobs_ts.py`

- [ ] **Step 1: Esegui tutta la test suite**

```bash
python -m pytest tests/ -v
```
Atteso: tutti PASS

- [ ] **Step 2: Verifica manualmente il dry run**

```bash
echo "RANDOMIZ          1.  12345678" > /tmp/test_sim.inp
python launch_jobs.py --help
python launch_jobs.py ts --help
python launch_jobs.py ts -f /tmp/test_sim.inp -n 2 -w
```
Atteso: tabella colorata, poi due righe "Job 1: [dry run] ts rfluka ..." e "Job 2: ..."

- [ ] **Step 3: Elimina i vecchi script**

```bash
git rm scripts/launch_jobs_lsf.py scripts/launch_jobs_slurm.py scripts/launch_jobs_htcondor.py scripts/launch_jobs_ts.py
```

- [ ] **Step 4: Commit finale**

```bash
git add -A
git commit -m "refactor: replace 4 standalone scripts with unified launch_jobs.py + backend system"
```
