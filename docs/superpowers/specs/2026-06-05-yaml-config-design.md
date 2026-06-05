# Design: Supporto configurazione YAML e lancio da cartella

**Data:** 2026-06-05
**Progetto:** FlukaQueueSub
**Branch:** main

---

## Obiettivo

Aggiungere a `launch_jobs.py` due nuove modalità di invocazione:

1. **YAML mode** — `python launch_jobs.py config.yaml` — legge tutti i parametri da un file YAML
2. **Folder mode** — `python launch_jobs.py configs/` — esegue in sequenza tutti i `.yaml`/`.yml` trovati nella cartella

Il comportamento CLI esistente (`python launch_jobs.py lsf -f sim.inp -n 10 ...`) resta invariato.

---

## Rilevamento della modalità

All'ingresso di `main()`, prima di invocare argparse:

```
sys.argv[1] ends with ".yaml" or ".yml"  →  YAML mode
os.path.isdir(sys.argv[1])               →  Folder mode
altrimenti                               →  CLI mode (comportamento attuale)
```

Se `len(sys.argv) < 2`, si cade nel CLI mode e argparse mostra il messaggio di aiuto.

---

## Schema YAML

Struttura piatta. I nomi delle chiavi corrispondono esattamente agli attributi del `Namespace` argparse.

### Campi comuni (tutti i backend)

| Chiave | Tipo | Obbligatorio | Default |
|---|---|---|---|
| `backend` | str | sì | — |
| `input` | str | sì | — |
| `njobs` | int | sì | — |
| `dry_run` | bool | no | `false` |
| `custom_exe` | str o null | no | `null` |
| `output_dir` | str o null | no | `null` |

### Campi LSF

| Chiave | Default |
|---|---|
| `queue` | `"normal"` |
| `mem` | `"1500"` |
| `ntasks` | `1` |
| `time` | `"1-00:00:00"` |

### Campi Slurm

| Chiave | Default |
|---|---|
| `queue` | `"production"` |
| `mem` | `"1500"` |
| `ntasks` | `1` |
| `nodes` | `1` |
| `time` | `"1-00:00:00"` |

### Campi HTCondor

| Chiave | Default |
|---|---|
| `queue` | `"vanilla"` |
| `mem` | `"1500"` |
| `ncpu` | `1` |
| `disk` | `100000` |
| `time` | `86400` |
| `transfer_files` | `"yes"` |
| `output` | `"job_$(Cluster)_$(Process).out"` |
| `error` | `"job_$(Cluster)_$(Process).err"` |
| `log` | `"job_$(Cluster)_$(Process).log"` |

### Campi Task Spooler

Nessun campo specifico. Solo i campi comuni.

### Esempi

```yaml
# LSF
backend: lsf
input: simulation.inp
njobs: 10
queue: normal
mem: "1500"
ntasks: 1
time: "1-00:00:00"
```

```yaml
# Slurm con custom exe e dry run
backend: slurm
input: simulation.inp
njobs: 5
dry_run: true
custom_exe: /path/to/myexe
queue: production
mem: "2000"
nodes: 1
ntasks: 1
time: "0-12:00:00"
```

```yaml
# Task Spooler (minimo)
backend: ts
input: simulation.inp
njobs: 3
```

---

## Architettura: `core/config.py`

Funzione pubblica unica:

```python
def load_yaml_config(path: str, backends: dict[str, QueueBackend]) -> Namespace:
```

**Algoritmo:**

1. Legge il file YAML con `yaml.safe_load`
2. Estrae `backend` dal dict; errore se mancante o non in `backends`
3. Costruisce un `ArgumentParser` temporaneo, aggiunge i campi comuni (con `default=None` per i required), chiama `backend.add_args(parser)` per i campi specifici
4. `defaults = vars(parser.parse_args([]))` — ottiene tutti i default dal parser senza passare argomenti
5. `defaults.update(yaml_dict)` — sovrascrive con i valori del YAML
6. Valida che `input` e `njobs` siano presenti (non None); lancia `ValueError` se mancano
7. Restituisce `Namespace(**defaults)`

Questo approccio riusa `backend.add_args()` come unica fonte dei default backend-specifici, evitando duplicazione.

**Dipendenza circolare evitata:** `config.py` non importa `BACKENDS` da `launch_jobs.py`. Riceve il dizionario come parametro dalla funzione chiamante.

---

## Modifiche a `launch_jobs.py`

### Fattorizzazione interna

Il loop di lancio viene estratto in `_execute_jobs(args)`. Le funzioni pubbliche lo compongono diversamente:

```
_execute_jobs(args)       ← solo il loop job (setup_output_dir + for each job)
run_from_args(args)       ← validate + tabella + confirm + _execute_jobs  (usata da CLI e YAML mode)
run_folder(folder)        ← carica tutti i YAML, mostra sommario, confirm una volta, _execute_jobs per ciascuno
```

`main()` diventa:

```python
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
    # CLI mode
    parser = _build_parser()
    args = parser.parse_args()
    run_from_args(args)
```

### Folder mode: `run_folder`

```python
def run_folder(folder: str) -> None:
```

**Comportamento:**

1. Raccoglie tutti i file `.yaml`/`.yml` nella cartella (non ricorsivo), ordinati alfabeticamente
2. Se la cartella è vuota (nessun file YAML), logga un warning ed esce
3. Per ciascun file, chiama `load_yaml_config()` e `backend.validate()` — logga un errore e salta se il file non è valido
4. Mostra un riepilogo compatto: una riga per file (`nome file | backend | njobs`)
5. Chiede conferma una sola volta: `"Procedere con N lanci? (yes/no)"`
6. Chiama `_execute_jobs(args)` per ciascun file in sequenza
7. Se `_execute_jobs()` solleva un'eccezione su un file, logga l'errore e continua con il successivo

### Argomenti extra in YAML mode ignorati

`python launch_jobs.py config.yaml --njobs 5` — gli argomenti dopo il file YAML vengono ignorati. Il file YAML è la sola fonte di configurazione in YAML mode.

---

## Nuova dipendenza

`pyyaml` — aggiunto a `requirements.txt` (nuovo file).

```
pyyaml>=6.0
colorama
tabulate
```

---

## File modificati/aggiunti

| File | Azione |
|---|---|
| `core/config.py` | Nuovo — `load_yaml_config(path, backends) -> Namespace` |
| `launch_jobs.py` | Modifica — detection logic, `run_from_args()`, `run_folder()` |
| `tests/core/test_config.py` | Nuovo — test per `load_yaml_config` |
| `tests/test_launch_jobs.py` | Modifica — test per YAML mode e folder mode |
| `requirements.txt` | Nuovo — `pyyaml>=6.0`, `colorama`, `tabulate` |

---

## Compatibilità

Il comportamento CLI esistente è invariato. Nessun argomento, flag, o file esistente viene modificato.
