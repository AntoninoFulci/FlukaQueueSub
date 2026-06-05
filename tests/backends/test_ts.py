import pytest
from argparse import Namespace
from unittest.mock import patch
from backends.ts import TSBackend
from backends.base import JobInfo

BACKEND = TSBackend()

def make_args(**kwargs):
    defaults = dict(dry_run=False, custom_exe=None)
    defaults.update(kwargs)
    return Namespace(**defaults)

def test_validate_does_not_raise():
    BACKEND.validate(make_args())

def test_generate_script_returns_none(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    result = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert result is None

def test_submit_dry_run_contains_ts_and_rfluka():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
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
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "3"
        result = BACKEND.submit(None, job_info, make_args(dry_run=False))
    assert "3" in result
    assert mock_run.call_args[0][0].startswith("ts ")
    assert "rfluka" in mock_run.call_args[0][0]

def test_submit_raises_on_failure():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "ts: command not found"
        with pytest.raises(RuntimeError, match="ts: command not found"):
            BACKEND.submit(None, job_info, make_args(dry_run=False))

def test_table_rows_returns_list():
    rows = BACKEND.table_rows(make_args(), "/bin", "/fluka")
    assert isinstance(rows, list)
