import subprocess
import pytest
from pathlib import Path

from collect_results import discover_sim_dirs, collect_sim_dir

SCRIPT = Path(__file__).resolve().parent.parent / "collect_results.py"


def make_sim_dir(tmp_path, sim_name, jobs):
    """Create a fake simulation directory tree.

    jobs: dict of {job_dir_name: [list of filenames]}
    """
    sim_dir = tmp_path / sim_name
    sim_dir.mkdir()
    (sim_dir / f"{sim_name}.inp").touch()
    for job_name, files in jobs.items():
        job_dir = sim_dir / job_name
        job_dir.mkdir()
        for f in files:
            (job_dir / f).touch()
    return sim_dir


def test_discover_finds_matching_dirs(tmp_path):
    (tmp_path / "01a.Simulation_Lead").mkdir()
    (tmp_path / "01a.Simulation_Mercury").mkdir()
    (tmp_path / "configs").mkdir()
    result = discover_sim_dirs(tmp_path, "*Simulation*")
    assert len(result) == 2
    assert all("Simulation" in p.name for p in result)


def test_discover_ignores_files(tmp_path):
    (tmp_path / "01a.Simulation_Lead").mkdir()
    (tmp_path / "01a.Simulation_Lead.inp").touch()
    result = discover_sim_dirs(tmp_path, "*Simulation*")
    assert len(result) == 1
    assert result[0].is_dir()


def test_discover_custom_pattern(tmp_path):
    (tmp_path / "MyRun").mkdir()
    (tmp_path / "other").mkdir()
    result = discover_sim_dirs(tmp_path, "MyRun*")
    assert len(result) == 1
    assert result[0].name == "MyRun"


def test_discover_returns_sorted(tmp_path):
    (tmp_path / "01b.Simulation_B").mkdir()
    (tmp_path / "01a.Simulation_A").mkdir()
    result = discover_sim_dirs(tmp_path, "*Simulation*")
    assert result[0].name == "01a.Simulation_A"
    assert result[1].name == "01b.Simulation_B"


def test_collect_moves_root_files_to_root_files_dir(tmp_path):
    sim_dir = make_sim_dir(tmp_path, "01a.Simulation_Lead", {
        "job_0001": ["01a.Simulation_Lead_0001001_dump.root", "01a.Simulation_Lead_0001.inp", "job_0001.sh"],
        "job_0002": ["01a.Simulation_Lead_0002001_dump.root", "01a.Simulation_Lead_0002.inp", "job_0002.sh"],
    })
    moved, deleted = collect_sim_dir(sim_dir, dry_run=False)
    assert moved == 2
    assert (sim_dir / "root_files" / "01a.Simulation_Lead_0001001_dump.root").exists()
    assert (sim_dir / "root_files" / "01a.Simulation_Lead_0002001_dump.root").exists()


def test_collect_deletes_job_dirs(tmp_path):
    sim_dir = make_sim_dir(tmp_path, "01a.Simulation_Lead", {
        "job_0001": ["file.root"],
        "job_0002": ["file2.root"],
    })
    moved, deleted = collect_sim_dir(sim_dir, dry_run=False)
    assert deleted == 2
    assert not (sim_dir / "job_0001").exists()
    assert not (sim_dir / "job_0002").exists()


def test_collect_leaves_top_level_inp_untouched(tmp_path):
    sim_dir = make_sim_dir(tmp_path, "01a.Simulation_Lead", {
        "job_0001": ["file.root"],
    })
    collect_sim_dir(sim_dir, dry_run=False)
    assert (sim_dir / "01a.Simulation_Lead.inp").exists()


def test_collect_returns_moved_and_deleted_counts(tmp_path):
    sim_dir = make_sim_dir(tmp_path, "01a.Simulation_Lead", {
        "job_0001": ["a.root", "b.root"],
        "job_0002": ["c.root"],
    })
    moved, deleted = collect_sim_dir(sim_dir, dry_run=False)
    assert moved == 3
    assert deleted == 2
