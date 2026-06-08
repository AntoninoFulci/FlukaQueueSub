from argparse import ArgumentParser, Namespace

import yaml

from backends.base import QueueBackend


def load_yaml_config(path: str, backends: dict[str, QueueBackend]) -> Namespace:
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
    parser.add_argument("--nprim",      dest="nprim",      type=int, default=None)
    backend.add_args(parser)

    defaults = vars(parser.parse_args([]))
    defaults.update(data)
    defaults["backend"] = backend_name

    if defaults.get("njobs") is not None:
        try:
            defaults["njobs"] = int(defaults["njobs"])
        except (ValueError, TypeError):
            raise ValueError(f"'njobs' deve essere un intero, trovato: {defaults.get('njobs')!r}")
        if defaults["njobs"] < 1:
            raise ValueError(f"'njobs' deve essere >= 1, trovato: {defaults['njobs']}")

    if defaults.get("input") is None:
        raise ValueError(f"Campo 'input' mancante in {path!r}")
    if not str(defaults["input"]).endswith(".inp"):
        raise ValueError(f"Il file di input deve terminare con .inp: {defaults['input']!r}")
    if defaults.get("njobs") is None:
        raise ValueError(f"Campo 'njobs' mancante in {path!r}")

    return Namespace(**defaults)
