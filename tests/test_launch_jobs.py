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

    # Two YAMLs with the same input create two output dirs (sim/ and sim_1/)
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
    assert len(output_dirs) == 1  # only good.yaml creates a dir


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
    assert len(output_dirs) == 0  # no jobs executed
