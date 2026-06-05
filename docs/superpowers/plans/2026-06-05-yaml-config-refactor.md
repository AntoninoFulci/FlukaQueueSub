# YAML Config & Folder Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere a FlukaQueueSub il supporto per file di configurazione YAML e lancio batch da cartella, mantenendo invariato il comportamento CLI esistente.

**Architecture:** Un nuovo modulo `core/config.py` espone `load_yaml_config(path, backends) -> Namespace`, che costruisce un parser temporaneo per estrarre i default di ogni backend senza duplicazione. `launch_jobs.py` viene refactored: il loop di lancio viene estratto in `_execute_jobs(args, fluka_path)`, la pipeline completa in `run_from_args(args)`, e `main()` aggiunge la detection logic per YAML e folder mode.

**Tech Stack:** Python 3.10+, `pyyaml>=6.0`, `argparse` (stdlib), `pytest`

---

## File coinvolti

| File | Azione |
|---|---|
| `requirements.txt` | Nuovo — dipendenze del progetto |
| `core/config.py` | Nuovo — `load_yaml_config(path, backends) -> Namespace` |
| `tests/core/test_config.py` | Nuovo — test per `load_yaml_config` |
| `launch_jobs.py` | Modifica — estrai `_execute_jobs`, `run_from_args`; aggiungi detection logic e `run_folder` |
| `tests/test_launch_jobs.py` | Modifica — aggiungi test YAML mode e folder mode |

---

## Contesto del progetto

Il progetto ha questa struttura:

```
launch_jobs.py              <- entrypoint (da modificare)
core/
  fluka.py                  <- detect_fluka_path(), generate_input()
  filesystem.py             <- setup_output_dir(), setup_job_dir()
  display.py                <- COLORS, print_table(), confirm(prompt)
  utils.py                  <- parse_time_to_seconds()
backends/
  base.py                   <- QueueBackend ABC + JobInfo dataclass
  lsf.py                    <- LSFBackend (args: queue, mem, ntasks, time)
  slurm.py                  <- SlurmBackend (args: queue, mem, ntasks, nodes, time)
  htcondor.py               <- HTCondorBackend (args: queue, mem, ncpu, disk, time, transfer_files, output, error, log)
  ts.py                     <- TSBackend (nessun arg specifico)
tests/
  test_launch_jobs.py       <- test esistenti (da estendere)
  core/
    test_config.py          <- nuovo
```

Ogni backend implementa `add_args(parser)` che aggiunge i propri argomenti CLI al subparser con i relativi default.

Il `Namespace` prodotto dall'argparse ha questi attributi comuni:
- `backend`: str
- `input`: str
- `njobs`: int
- `custom_exe`: str | None
- `dry_run`: bool
- `output_dir`: str | None

---

## Task 1: requirements.txt

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Crea requirements.txt**

```
pyyaml>=6.0
colorama
tabulate
```

Percorso: `/Users/tonyf/Work/FlukaQueueSub/requirements.txt`

- [ ] **Step 2: Installa pyyaml**

```bash
pip install pyyaml
```

Verifica: `python -c "import yaml; print(yaml.__version__)"` → deve stampare `6.x`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add requirements.txt with pyyaml dependency"
```

---

## Task 2: core/config.py

**Files:**
- Create: `core/config.py`
- Create: `tests/core/test_config.py`

**Dipendenza:** nessuna (indipendente da launch_jobs.py)

- [ ] **Step 1: Scrivi i test (fallenti)**

Crea `tests/core/test_config.py`:

```python
import pytest
import yaml
from argparse import Namespace


def make_yaml(tmp_path, content: dict) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(content))
    return str(path)


def test_load_ts_minimal(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"backend": "ts", "input": "sim.inp", "njobs": 5})
    args = load_yaml_config(path, backends)
    assert args.backend == "ts"
    assert args.input == "sim.inp"
    assert args.njobs == 5
    assert args.dry_run is False
    assert args.custom_exe is None
    assert args.output_dir is None


def test_load_lsf_uses_backend_defaults(tmp_path):
    from core.config import load_yaml_config
    from backends.lsf import LSFBackend
    backends = {"lsf": LSFBackend()}
    path = make_yaml(tmp_path, {"backend": "lsf", "input": "sim.inp", "njobs": 1})
    args = load_yaml_config(path, backends)
    assert args.queue == "normal"
    assert args.mem == "1500"
    assert args.ntasks == 1
    assert args.time == "1-00:00:00"


def test_load_lsf_overrides_defaults(tmp_path):
    from core.config import load_yaml_config
    from backends.lsf import LSFBackend
    backends = {"lsf": LSFBackend()}
    path = make_yaml(tmp_path, {
        "backend": "lsf", "input": "sim.inp", "njobs": 10,
        "queue": "priority", "mem": "3000", "ntasks": 4, "time": "2-00:00:00",
    })
    args = load_yaml_config(path, backends)
    assert args.queue == "priority"
    assert args.mem == "3000"
    assert args.ntasks == 4
    assert args.time == "2-00:00:00"


def test_load_slurm_defaults(tmp_path):
    from core.config import load_yaml_config
    from backends.slurm import SlurmBackend
    backends = {"slurm": SlurmBackend()}
    path = make_yaml(tmp_path, {"backend": "slurm", "input": "sim.inp", "njobs": 1})
    args = load_yaml_config(path, backends)
    assert args.queue == "production"
    assert args.nodes == 1
    assert args.ntasks == 1


def test_dry_run_parsed(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"backend": "ts", "input": "sim.inp", "njobs": 1, "dry_run": True})
    args = load_yaml_config(path, backends)
    assert args.dry_run is True


def test_custom_exe_parsed(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {
        "backend": "ts", "input": "sim.inp", "njobs": 1, "custom_exe": "/path/to/exe"
    })
    args = load_yaml_config(path, backends)
    assert args.custom_exe == "/path/to/exe"


def test_missing_backend_raises(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"input": "sim.inp", "njobs": 1})
    with pytest.raises(ValueError, match="backend"):
        load_yaml_config(path, backends)


def test_unknown_backend_raises(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"backend": "unknown", "input": "sim.inp", "njobs": 1})
    with pytest.raises(ValueError, match="sconosciuto"):
        load_yaml_config(path, backends)


def test_missing_input_raises(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"backend": "ts", "njobs": 1})
    with pytest.raises(ValueError, match="input"):
        load_yaml_config(path, backends)


def test_missing_njobs_raises(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"backend": "ts", "input": "sim.inp"})
    with pytest.raises(ValueError, match="njobs"):
        load_yaml_config(path, backends)
```

- [ ] **Step 2: Verifica che i test falliscano**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/core/test_config.py -v
```

Expected: tutti FAIL con `ModuleNotFoundError` o `ImportError`

- [ ] **Step 3: Implementa core/config.py**

```python
from argparse import ArgumentParser, Namespace

import yaml


def load_yaml_config(path: str, backends: dict) -> Namespace:
    with open(path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Il file YAML deve contenere un dizionario: {path!r}")

    backend_name = data.get("backend")
    if not backend_name:
        raise ValueError(f"Campo 'backend' mancante in {path!r}")
    if backend_name not in backends:
        raise ValueError(
            f"Backend sconosciuto {backend_name!r}. Disponibili: {sorted(backends)}"
        )

    backend = backends[backend_name]

    # Costruisce un parser temporaneo per estrarre i default del backend
    parser = ArgumentParser()
    parser.add_argument("--input",      dest="input",      default=None)
    parser.add_argument("--njobs",      dest="njobs",      type=int, default=None)
    parser.add_argument("--custom-exe", dest="custom_exe", default=None)
    parser.add_argument("--dry-run",    dest="dry_run",    action="store_true", default=False)
    parser.add_argument("--output-dir", dest="output_dir", default=None)
    backend.add_args(parser)

    defaults = vars(parser.parse_args([]))
    defaults.update(data)
    defaults["backend"] = backend_name

    if defaults.get("input") is None:
        raise ValueError(f"Campo 'input' mancante in {path!r}")
    if defaults.get("njobs") is None:
        raise ValueError(f"Campo 'njobs' mancante in {path!r}")

    return Namespace(**defaults)
```

Percorso: `core/config.py`

- [ ] **Step 4: Verifica che i test passino**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/core/test_config.py -v
```

Expected: tutti PASS

- [ ] **Step 5: Verifica che la suite completa non regredisca**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest -v
```

Expected: tutti i test precedenti PASS + i nuovi 10

- [ ] **Step 6: Commit**

```bash
git add core/config.py tests/core/test_config.py
git commit -m "feat: add core/config.py with load_yaml_config()"
```

---

## Task 3: Refactor launch_jobs.py + YAML mode

**Files:**
- Modify: `launch_jobs.py`
- Modify: `tests/test_launch_jobs.py`

**Dipendenza:** Task 2 deve essere completato (richiede `core/config.py`)

Il task ha due parti:
1. Refactoring puro: estrai `_execute_jobs` e `run_from_args` dall'attuale `main()` — i test esistenti devono continuare a passare
2. Aggiungi YAML mode: detection in `main()` + nuovi test

- [ ] **Step 1: Aggiungi i test YAML mode (fallenti)**

Aggiungi in fondo a `tests/test_launch_jobs.py`:

```python
import yaml as _yaml


def test_yaml_mode_ts_dry_run(tmp_path, monkeypatch):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    cfg = tmp_path / "config.yaml"
    cfg.write_text(_yaml.dump({
        "backend": "ts", "input": str(inp), "njobs": 2, "dry_run": True
    }))

    monkeypatch.chdir(tmp_path)
    sys.argv = ["launch_jobs.py", str(cfg)]

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dir = tmp_path / "sim"
    assert output_dir.is_dir()
    assert len(list(output_dir.iterdir())) == 2


def test_yaml_mode_lsf_dry_run(tmp_path, monkeypatch):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    cfg = tmp_path / "config.yaml"
    cfg.write_text(_yaml.dump({
        "backend": "lsf", "input": str(inp), "njobs": 2, "dry_run": True
    }))

    monkeypatch.chdir(tmp_path)
    sys.argv = ["launch_jobs.py", str(cfg)]

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    sh_files = list((tmp_path / "sim").rglob("*.sh"))
    assert len(sh_files) == 2


def test_yaml_mode_invalid_input_extension_exits(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(_yaml.dump({"backend": "ts", "input": "sim.txt", "njobs": 1}))

    sys.argv = ["launch_jobs.py", str(cfg)]

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        with pytest.raises(SystemExit):
            launch_jobs.main()
```

- [ ] **Step 2: Verifica che i nuovi test falliscano**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/test_launch_jobs.py -v -k "yaml"
```

Expected: FAIL (YAML mode non ancora implementato)

- [ ] **Step 3: Riscrivi launch_jobs.py con refactoring + YAML mode**

Sostituisci il contenuto di `launch_jobs.py` con:

```python
#!/usr/bin/env python3

import logging
import os
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter

from backends.base import JobInfo
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


def _execute_jobs(args: Namespace, fluka_path: str) -> None:
    backend = BACKENDS[args.backend]
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    output_dir = filesystem.setup_output_dir(base_name, args.output_dir)

    for i in range(1, args.njobs + 1):
        job_dir = filesystem.setup_job_dir(output_dir, i, args.input)
        new_input = fluka.generate_input(base_name, i, job_dir)
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
        ["-w", f"{C['Y']}Dry run{C['RE']}",     f"{C['Y']}{args.dry_run}{C['RE']}"],
    ]
    display.print_table(common_rows + backend.table_rows(args, fluka_path, fluka_folder))

    if not display.confirm():
        logging.info("Lancio annullato.")
        sys.exit(0)

    _execute_jobs(args, fluka_path)


def run_folder(folder: str) -> None:
    pass  # implementato nel Task 4


def main() -> None:
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg.endswith((".yaml", ".yml")):
            args = config.load_yaml_config(first_arg, BACKENDS)
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
```

- [ ] **Step 4: Verifica che i test esistenti continuino a passare**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/test_launch_jobs.py -v -k "not yaml and not folder"
```

Expected: tutti PASS

- [ ] **Step 5: Verifica che i nuovi test YAML passino**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/test_launch_jobs.py -v -k "yaml"
```

Expected: tutti PASS

- [ ] **Step 6: Verifica la suite completa**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest -v
```

Expected: tutti PASS

- [ ] **Step 7: Commit**

```bash
git add launch_jobs.py tests/test_launch_jobs.py
git commit -m "feat: refactor launch_jobs.py and add YAML config mode"
```

---

## Task 4: Folder mode

**Files:**
- Modify: `launch_jobs.py` — implementa `run_folder()`
- Modify: `tests/test_launch_jobs.py` — aggiungi test folder mode

**Dipendenza:** Task 3 deve essere completato

- [ ] **Step 1: Aggiungi i test folder mode (fallenti)**

Aggiungi in fondo a `tests/test_launch_jobs.py`:

```python
def test_folder_mode_runs_all_yamls(tmp_path, monkeypatch):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    for name in ["a.yaml", "b.yaml"]:
        (configs_dir / name).write_text(_yaml.dump({
            "backend": "ts", "input": str(inp), "njobs": 1, "dry_run": True,
        }))

    monkeypatch.chdir(tmp_path)
    sys.argv = ["launch_jobs.py", str(configs_dir)]

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    # Due YAML con lo stesso input creano due output dir (sim/ e sim_1/)
    output_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name != "configs"]
    assert len(output_dirs) == 2


def test_folder_mode_empty_dir_warns(tmp_path, caplog):
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()

    sys.argv = ["launch_jobs.py", str(configs_dir)]

    import launch_jobs
    import importlib
    importlib.reload(launch_jobs)

    import logging
    with caplog.at_level(logging.WARNING):
        launch_jobs.main()

    assert "Nessun file YAML" in caplog.text


def test_folder_mode_skips_invalid_continues_valid(tmp_path, monkeypatch, caplog):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "bad.yaml").write_text(
        _yaml.dump({"backend": "nonexistent", "input": str(inp), "njobs": 1})
    )
    (configs_dir / "good.yaml").write_text(
        _yaml.dump({"backend": "ts", "input": str(inp), "njobs": 1, "dry_run": True})
    )

    monkeypatch.chdir(tmp_path)
    sys.argv = ["launch_jobs.py", str(configs_dir)]

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        import logging
        with caplog.at_level(logging.ERROR):
            launch_jobs.main()

    assert "non valido" in caplog.text
    output_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name != "configs"]
    assert len(output_dirs) == 1  # solo il good.yaml crea una dir


def test_folder_mode_cancelled_by_user(tmp_path, monkeypatch):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "a.yaml").write_text(
        _yaml.dump({"backend": "ts", "input": str(inp), "njobs": 1, "dry_run": True})
    )

    monkeypatch.chdir(tmp_path)
    sys.argv = ["launch_jobs.py", str(configs_dir)]

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=False):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name != "configs"]
    assert len(output_dirs) == 0  # nessun job eseguito
```

- [ ] **Step 2: Verifica che i test folder mode falliscano**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/test_launch_jobs.py -v -k "folder"
```

Expected: FAIL (run_folder e' ancora `pass`)

- [ ] **Step 3: Implementa run_folder() in launch_jobs.py**

Sostituisci il corpo di `run_folder` (il `pass`) con:

```python
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
            args = config.load_yaml_config(path, BACKENDS)
            BACKENDS[args.backend].validate(args)
            configs.append((path, args))
        except Exception as e:
            logging.error("File %r non valido: %s", path, e)

    if not configs:
        logging.error("Nessuna configurazione valida trovata.")
        return

    C = display.COLORS
    rows = [["File", "Backend", "N. job"]]
    for path, args in configs:
        rows.append([
            os.path.basename(path),
            f"{C['M']}{args.backend}{C['RE']}",
            f"{C['M']}{args.njobs}{C['RE']}",
        ])
    display.print_table(rows)

    if not display.confirm(f"Procedere con {len(configs)} lanci? (yes/no): "):
        logging.info("Lancio annullato.")
        return

    fluka_path, _ = fluka.detect_fluka_path()
    for path, args in configs:
        try:
            logging.info("Avvio: %s", os.path.basename(path))
            _execute_jobs(args, fluka_path)
        except Exception as e:
            logging.error("Errore in %r: %s", path, e)
```

- [ ] **Step 4: Verifica che i test folder mode passino**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest tests/test_launch_jobs.py -v -k "folder"
```

Expected: tutti PASS

- [ ] **Step 5: Verifica la suite completa**

```bash
cd /Users/tonyf/Work/FlukaQueueSub && pytest -v
```

Expected: tutti PASS (inclusi i test pre-esistenti)

- [ ] **Step 6: Commit**

```bash
git add launch_jobs.py tests/test_launch_jobs.py
git commit -m "feat: add folder mode to launch_jobs.py"
```

---

## Self-review checklist

- [x] **Spec coverage:**
  - YAML mode detection -> Task 3, Step 3 (main() detection logic)
  - Folder mode detection -> Task 3, Step 3 + Task 4, Step 3
  - core/config.py con load_yaml_config -> Task 2
  - Schema YAML (tutti i backend con default) -> Task 2 test + Task 2 Step 3
  - Cartella vuota -> warning -> Task 4 test test_folder_mode_empty_dir_warns
  - File invalido -> skip + continua -> Task 4 test test_folder_mode_skips_invalid_continues_valid
  - Conferma unica per folder -> Task 4 test test_folder_mode_cancelled_by_user
  - requirements.txt -> Task 1
  - Argomenti extra in YAML mode ignorati -> comportamento naturale: sys.argv[1] e' il YAML, il resto non viene letto
  - Compatibilita' CLI -> test esistenti coperti in Task 3, Step 4
- [x] **Nessun placeholder**
- [x] **Consistenza dei tipi:** _execute_jobs(args: Namespace, fluka_path: str) usata in Task 3 e Task 4 con la stessa firma
