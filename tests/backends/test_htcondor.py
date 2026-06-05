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
        time=86400, dry_run=False, custom_exe=None,
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
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    script = BACKEND.generate_script(job_info, str(tmp_path), make_args())
    assert os.path.isfile(script)
    assert script.endswith("job_0001.sh")

def test_generate_script_contains_rfluka(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    content = open(BACKEND.generate_script(job_info, str(tmp_path), make_args())).read()
    assert "rfluka" in content

def test_submit_dry_run_returns_description():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    result = BACKEND.submit("/tmp/job.sh", job_info, make_args(dry_run=True))
    assert "dry run" in result.lower()
    assert "condor" in result.lower()

def test_submit_calls_schedd(tmp_path):
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
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

def test_submit_raises_if_htcondor_not_installed():
    job_info = JobInfo("sim_0001.inp", 1, "/usr/local/fluka/bin", None)
    with patch("backends.htcondor.htcondor", None):
        with pytest.raises(RuntimeError, match="htcondor"):
            BACKEND.submit("/tmp/job.sh", job_info, make_args(dry_run=False))

def test_table_rows_returns_list():
    rows = BACKEND.table_rows(make_args(), "/bin", "/fluka")
    assert isinstance(rows, list)
    assert len(rows) > 0
