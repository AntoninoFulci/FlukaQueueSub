import os
import pytest
from core.filesystem import setup_output_dir, setup_job_dir


def test_setup_output_dir_creates_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = setup_output_dir("myrun", None)
    assert result == "myrun"
    assert os.path.isdir(result)


def test_setup_output_dir_uses_custom_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = setup_output_dir("myrun", "custom_output")
    assert result == "custom_output"
    assert os.path.isdir(result)


def test_setup_output_dir_avoids_collision(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_output_dir("myrun", None)
    result = setup_output_dir("myrun", None)
    assert result == "myrun_1"
    assert os.path.isdir(result)


def test_setup_output_dir_multiple_collisions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_output_dir("run", None)
    setup_output_dir("run", None)
    result = setup_output_dir("run", None)
    assert result == "run_2"


def test_setup_job_dir_creates_subdirectory(tmp_path):
    output_dir = str(tmp_path / "output")
    os.makedirs(output_dir)
    inp = tmp_path / "sim.inp"
    inp.write_text("content")

    job_dir = setup_job_dir(output_dir, 1, str(inp))

    assert os.path.isabs(job_dir)
    assert os.path.isdir(job_dir)
    assert os.path.basename(job_dir) == "job_0001"
    assert os.path.isfile(os.path.join(job_dir, "sim.inp"))


def test_setup_job_dir_zero_pads_iteration(tmp_path):
    output_dir = str(tmp_path / "output")
    os.makedirs(output_dir)
    inp = tmp_path / "sim.inp"
    inp.write_text("x")

    job_dir = setup_job_dir(output_dir, 7, str(inp))
    assert os.path.basename(job_dir) == "job_0007"
