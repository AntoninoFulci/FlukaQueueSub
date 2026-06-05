import sys
import pytest
import yaml as _yaml
from unittest.mock import patch


def test_no_subcommand_exits(capsys):
    sys.argv = ["launch_jobs.py"]
    import launch_jobs
    import importlib
    importlib.reload(launch_jobs)
    with pytest.raises(SystemExit):
        launch_jobs.main()


def test_invalid_extension_exits():
    sys.argv = ["launch_jobs.py", "ts", "-f", "input.txt", "-n", "1"]
    import launch_jobs
    import importlib
    importlib.reload(launch_jobs)
    with pytest.raises(SystemExit):
        launch_jobs.main()


def test_ts_dry_run_creates_job_dirs(tmp_path, monkeypatch):
    inp = tmp_path / "myinput.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    sys.argv = ["launch_jobs.py", "ts", "-f", str(inp), "-n", "3", "-w"]
    monkeypatch.chdir(tmp_path)

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dir = tmp_path / "myinput"
    assert output_dir.is_dir()
    assert len(list(output_dir.iterdir())) == 3


def test_lsf_dry_run_creates_sh_files(tmp_path, monkeypatch):
    inp = tmp_path / "sim.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    sys.argv = ["launch_jobs.py", "lsf", "-f", str(inp), "-n", "2", "-w"]
    monkeypatch.chdir(tmp_path)

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dir = tmp_path / "sim"
    sh_files = list(output_dir.rglob("*.sh"))
    assert len(sh_files) == 2


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


def test_yaml_mode_missing_backend_exits(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(_yaml.dump({"input": "sim.inp", "njobs": 1}))  # no backend key

    sys.argv = ["launch_jobs.py", str(cfg)]

    import launch_jobs
    import importlib
    importlib.reload(launch_jobs)
    with pytest.raises(SystemExit):
        launch_jobs.main()
