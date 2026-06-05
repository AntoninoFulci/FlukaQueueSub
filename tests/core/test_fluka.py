import os
import pytest
from unittest.mock import patch
from core.fluka import generate_input, detect_fluka_path


def test_generate_input_renames_file(tmp_path):
    base = "simulation"
    inp = tmp_path / f"{base}.inp"
    inp.write_text("TITLE test\nRANDOMIZ          1.  12345678\nSTOP\n")

    result = generate_input(base, 1, str(tmp_path))

    assert result == f"{base}_0001.inp"
    assert not (tmp_path / f"{base}.inp").exists()
    assert (tmp_path / result).exists()


def test_generate_input_updates_randomiz_seed(tmp_path):
    base = "simulation"
    inp = tmp_path / f"{base}.inp"
    inp.write_text("RANDOMIZ          1.  12345678\n")

    generate_input(base, 1, str(tmp_path))

    content = (tmp_path / f"{base}_0001.inp").read_text()
    assert "RANDOMIZ" in content
    assert "12345678" not in content


def test_generate_input_zero_pads_iteration(tmp_path):
    base = "sim"
    (tmp_path / f"{base}.inp").write_text("RANDOMIZ          1.  99999999\n")
    result = generate_input(base, 42, str(tmp_path))
    assert result == "sim_0042.inp"


def test_detect_fluka_path_returns_paths():
    with patch("subprocess.check_output", side_effect=[b"/usr/local/bin\n", b"/usr/local/fluka\n"]):
        bin_path, folder_path = detect_fluka_path()
    assert bin_path == "/usr/local/bin"
    assert folder_path == "/usr/local/fluka"


def test_detect_fluka_path_exits_if_not_found():
    import subprocess
    with patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "fluka-config")):
        with pytest.raises(SystemExit):
            detect_fluka_path()


def test_generate_input_raises_if_no_randomiz(tmp_path):
    base = "sim"
    (tmp_path / f"{base}.inp").write_text("TITLE test\nSTOP\n")
    with pytest.raises(ValueError, match="RANDOMIZ"):
        generate_input(base, 1, str(tmp_path))


def test_detect_fluka_path_exits_if_command_missing():
    with patch("subprocess.check_output", side_effect=FileNotFoundError):
        with pytest.raises(SystemExit):
            detect_fluka_path()
