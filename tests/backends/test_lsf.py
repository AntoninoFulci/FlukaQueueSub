import os
import pytest
from argparse import Namespace
from unittest.mock import patch
from backends.lsf import LSFBackend
from backends.base import JobInfo

BACKEND = LSFBackend()

def make_args(**kwargs):
    defaults = dict(queue="normal", mem="1500", ntasks=1, time="1-00:00:00", dry_run=False, custom_exe=None)
    defaults.update(kwargs)
    return Namespace(**defaults)

def test_validate_accepts_valid_time():
    BACKEND.validate(make_args(time="1-00:00:00"))

def test_validate_rejects_time_over_max():
    with pytest.raises(ValueError, match="4-00:00:00"):
        BACKEND.validate(make_args(time="5-00:00:00"))

def test_generate_script_creates_sh_file(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    script = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert script.endswith("job_0001.sh")
    assert os.path.isfile(script)

def test_generate_script_contains_bsub_directives(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
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
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    result = BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=True))
    assert "dry run" in result.lower()
    assert "bsub" in result

def test_submit_calls_bsub():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Job <12345> is submitted"
        result = BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=False))
    assert "12345" in result
    assert "bsub" in mock_run.call_args[0][0]

def test_submit_raises_on_failure():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Queue not found"
        with pytest.raises(RuntimeError, match="Queue not found"):
            BACKEND.submit("/tmp/job_0001.sh", job_info, make_args(dry_run=False))

def test_table_rows_returns_list():
    rows = BACKEND.table_rows(make_args(), "/bin", "/fluka")
    assert isinstance(rows, list)
    assert len(rows) > 0
