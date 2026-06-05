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
    with pytest.raises(ValueError, match="unknown"):
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


def test_load_htcondor_defaults(tmp_path):
    from core.config import load_yaml_config
    from backends.htcondor import HTCondorBackend
    backends = {"condor": HTCondorBackend()}
    path = make_yaml(tmp_path, {"backend": "condor", "input": "sim.inp", "njobs": 1})
    args = load_yaml_config(path, backends)
    assert args.queue == "vanilla"
    assert args.mem == "1500"
    assert args.ncpu == 1
    assert args.disk == 100000
    assert args.time == 86400
    assert args.transfer_files == "yes"
    assert args.output == "job_$(Cluster)_$(Process).out"
    assert args.output_dir is None  # common arg, should be separate from args.output


def test_njobs_zero_raises(tmp_path):
    from core.config import load_yaml_config
    from backends.ts import TSBackend
    backends = {"ts": TSBackend()}
    path = make_yaml(tmp_path, {"backend": "ts", "input": "sim.inp", "njobs": 0})
    with pytest.raises(ValueError, match="njobs"):
        load_yaml_config(path, backends)
