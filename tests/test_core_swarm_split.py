import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import swarm_split  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARMTIER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    (tmp_path / "proj").mkdir()
    return tmp_path


def test_splits_into_batches_under_limit(tmp_path):
    d = tmp_path / "docs"
    d.mkdir()
    for i in range(6):
        (d / ("f%d.md" % i)).write_text("x" * 33000, encoding="utf-8")  # ~10k tokens each
    batches = swarm_split.split([str(d)], max_tokens=25000)
    assert len(batches) == 3
    assert all(b["tokens"] <= 25000 for b in batches)
    assert sum(len(b["items"]) for b in batches) == 6


def test_big_file_cut_by_line_range(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("".join("line %05d %s\n" % (i, "y" * 30) for i in range(2000)), encoding="utf-8")
    batches = swarm_split.split([str(f)], max_tokens=5000)
    labels = [i for b in batches for i in b["items"]]
    assert len(labels) > 1 and all("(l." in lab for lab in labels)
    assert labels[0] != labels[1]


def test_cli_english_help_and_exit_codes(tmp_path, capsys):
    with pytest.raises(SystemExit):
        swarm_split.main(["--help"])
    out = capsys.readouterr().out
    assert "targets" in out
    assert swarm_split.main([str(tmp_path / "nothing*.md")]) == 1
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    assert swarm_split.main([str(tmp_path / "a.md")]) == 0
    assert swarm_split.main([str(tmp_path / "a.md"), "--max", "999999"]) == 2
