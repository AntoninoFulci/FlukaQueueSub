import os
import sys
import pytest
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


def test_ts_dry_run_creates_job_dirs(tmp_path):
    inp = tmp_path / "myinput.inp"
    inp.write_text("RANDOMIZ          1.  12345678\nSTOP\n")

    sys.argv = ["launch_jobs.py", "ts", "-f", str(inp), "-n", "3", "-w"]
    os.chdir(tmp_path)

    with patch("core.fluka.detect_fluka_path", return_value=("/usr/local/bin", "/usr/local/fluka")), \
         patch("core.display.confirm", return_value=True):
        import launch_jobs
        import importlib
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
        import launch_jobs
        import importlib
        importlib.reload(launch_jobs)
        launch_jobs.main()

    output_dir = tmp_path / "sim"
    sh_files = list(output_dir.rglob("*.sh"))
    assert len(sh_files) == 2
