import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config  # noqa: E402


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARMTIER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "proj"))
    (tmp_path / "proj").mkdir()
    return tmp_path


def test_data_dir_uses_env_and_creates(home):
    d = config.data_dir()
    assert d == home / "home" and d.is_dir()


def test_defaults_public_keys():
    c = config.load_config()
    assert c["cache_ttl_minutes"] == 60
    assert c["swarm_max_tokens"] == 60000
    assert c["lessons_per_prompt"] == 3
    assert c["exempt_agents"] == []


def test_toml_overrides_and_mirrors(home):
    (home / "proj" / "swarmtier.toml").write_text(
        'swarm_max_tokens = 40000\nlessons_per_prompt = 2\nexempt_agents = ["a"]\n', encoding="utf-8")
    c = config.load_config()
    assert c["swarm"]["max_tokens"] == 40000
    assert c["learning"]["max_lessons_in_prompt"] == 2
    assert c["exempt_agents"] == ["a"]


def test_malformed_toml_falls_back(home):
    (home / "proj" / "swarmtier.toml").write_text("this is = = not toml [", encoding="utf-8")
    assert config.load_config()["swarm_max_tokens"] == 60000


def test_data_dir_from_toml(home, monkeypatch):
    monkeypatch.delenv("SWARMTIER_HOME")
    target = home / "elsewhere"
    (home / "proj" / "swarmtier.toml").write_text(
        'data_dir = "%s"\n' % target.as_posix(), encoding="utf-8")
    assert config.data_dir() == target


def test_jsonl_roundtrip_skips_corrupt(home):
    p = home / "x" / "f.jsonl"
    config.jsonl_append(p, {"a": 1, "t": "action"})
    with open(p, "a", encoding="utf-8") as f:
        f.write("{broken\n")
    config.jsonl_append(p, {"a": 2})
    assert [r["a"] for r in config.jsonl_read(p)] == [1, 2]
    assert config.jsonl_read(home / "missing.jsonl") == []
