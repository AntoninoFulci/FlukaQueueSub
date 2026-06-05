import pytest
from argparse import ArgumentParser, Namespace
from backends.base import QueueBackend, JobInfo


class ConcreteBackend(QueueBackend):
    def add_args(self, parser): pass
    def validate(self, args): pass
    def generate_script(self, job_info, job_dir, args): return "/tmp/job.sh"
    def submit(self, script_path, job_info, args): return "submitted"
    def table_rows(self, args, fluka_path, fluka_folder): return []


def test_jobinfo_fields():
    ji = JobInfo(input_file="sim_0001.inp", iteration=1, fluka_path="/usr/bin", custom_exe="None")
    assert ji.input_file == "sim_0001.inp"
    assert ji.iteration == 1


def test_cannot_instantiate_abstract_backend():
    with pytest.raises(TypeError):
        QueueBackend()


def test_concrete_backend_instantiates():
    b = ConcreteBackend()
    assert b.submit(None, JobInfo("f", 1, "/p", "None"), Namespace()) == "submitted"
