from unittest.mock import patch
from core.display import confirm, COLORS, print_table


def test_confirm_returns_true_on_yes():
    with patch("builtins.input", return_value="yes"):
        assert confirm() is True

def test_confirm_returns_true_on_y():
    with patch("builtins.input", return_value="y"):
        assert confirm() is True

def test_confirm_returns_false_on_no():
    with patch("builtins.input", return_value="no"):
        assert confirm() is False

def test_confirm_returns_false_on_other():
    with patch("builtins.input", return_value="maybe"):
        assert confirm() is False

def test_colors_dict_has_expected_keys():
    for key in ("G", "R", "Y", "B", "M", "C", "RE"):
        assert key in COLORS

def test_print_table_runs_without_error(capsys):
    rows = [["Command", "Parameter", "Value"], ["-f", "Input", "sim.inp"]]
    print_table(rows)
    out = capsys.readouterr().out
    assert "Input" in out
    assert "sim.inp" in out
