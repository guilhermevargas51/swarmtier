"""Paths, configuration and JSONL helpers shared by every swarmtier component.

Public API:
    data_dir() -> Path          state directory (SWARMTIER_HOME or ~/.swarmtier), created if missing
    project_dir() -> Path       user's project root (CLAUDE_PROJECT_DIR or cwd)
    load_config() -> dict       built-in defaults overlaid with swarmtier.toml (if any)
    jsonl_append(path, obj)     append one JSON object as one line
    jsonl_read(path) -> list    read all valid lines, skipping corrupt ones
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

try:  # Python 3.11+
    import tomllib as _toml
except ImportError:  # pragma: no cover - exercised only on 3.10
    _toml = None

CONFIG_FILENAME = "swarmtier.toml"

DEFAULTS: dict = {
    # Public keys (see templates/config.example.toml). They are the source of truth and
    # are mirrored into the internal sections below by load_config().
    "cache_ttl_minutes": 60,        # prompt cache goes cold after about this long
    "swarm_max_tokens": 60000,      # per swarm batch
    "lessons_per_prompt": 3,        # max lessons injected before a prompt
    "forbid_max_for": ["sonnet"],   # models where effort=max is refused by require-effort
    "cache_watch_min_tokens": 100000,  # Stop reminder to /compact only above this context size
    "exempt_agents": [],            # agents exempt from the require-effort hook
    "data_dir": "",                 # optional; default ~/.swarmtier or $SWARMTIER_HOME
    "swarm": {
        "max_tokens": 60000,        # mirrors swarm_max_tokens; above ~100k the small-model price tier jumps
        "hard_cap_tokens": 90000,   # refuse anything larger
        "max_agents": 15,           # above this, split into waves
        "chars_per_token": 3.3,
    },
    "learning": {
        "max_lessons_in_prompt": 3,
        "min_score": 3,
        "max_note_chars": 600,
        "retry_limit": 2,           # identical attempts before the 3rd is blocked
        "retry_window_min": 90,
    },
    "quota": {
        "cache_ttl_s": 300,         # reuse a reading this long instead of re-querying
        "stale_after_s": 900,       # readings older than this are flagged stale
        "pace_high": 1.15,          # spend/elapsed ratio above this = "above pace"
        "pace_low": 0.85,
        "week_days": 7,
    },
    "cold_cache": {
        "idle_minutes": 60,         # prompt cache goes cold after about this long
    },
}


def _configured_data_dir() -> str:
    """``data_dir`` from a project-root swarmtier.toml (read directly: config paths depend on data_dir)."""
    try:
        f = project_dir() / CONFIG_FILENAME
        if f.is_file():
            return str(_parse_toml(f).get("data_dir") or "")
    except Exception:
        pass
    return ""


def data_dir() -> Path:
    """State directory: ``SWARMTIER_HOME``, else ``data_dir`` in swarmtier.toml, else ``~/.swarmtier``.

    Created if missing.
    """
    chosen = os.environ.get("SWARMTIER_HOME") or _configured_data_dir()
    p = Path(chosen).expanduser() if chosen else Path.home() / ".swarmtier"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_dir() -> Path:
    """The user's project root: ``CLAUDE_PROJECT_DIR`` if set, else the current directory."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env).expanduser() if env else Path.cwd()


def _parse_toml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if _toml is not None:
        return _toml.loads(text)
    return _mini_toml(text)


def _mini_toml(text: str) -> dict:
    """Tiny fallback parser (3.10): ``[section]`` headers and ``key = scalar`` lines only."""
    out: dict = {}
    cur = out
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = out
            for part in line[1:-1].strip().split("."):
                cur = cur.setdefault(part.strip(), {})
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            parsed: object = [_mini_scalar(v.strip()) for v in inner.split(",") if v.strip()] if inner else []
        else:
            parsed = _mini_scalar(val)
        cur[key.strip()] = parsed
    return out


def _mini_scalar(val: str) -> object:
    if val.lower() in ("true", "false"):
        return val.lower() == "true"
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        return val[1:-1]
    try:
        return int(val.replace("_", ""))
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def config_paths() -> list[Path]:
    """Candidate config files, lowest priority first (SWARMTIER_HOME, then project root)."""
    return [data_dir() / CONFIG_FILENAME, project_dir() / CONFIG_FILENAME]


def load_config() -> dict:
    """Defaults overlaid with ``swarmtier.toml`` from SWARMTIER_HOME, then the project root.

    A missing or malformed file is ignored (defaults win); config must never break a hook.
    """
    cfg = copy.deepcopy(DEFAULTS)
    for p in config_paths():
        try:
            if p.is_file():
                _merge(cfg, _parse_toml(p))
        except Exception:
            continue
    cfg["swarm"]["max_tokens"] = cfg["swarm_max_tokens"]
    cfg["learning"]["max_lessons_in_prompt"] = cfg["lessons_per_prompt"]
    cfg["cold_cache"]["idle_minutes"] = cfg["cache_ttl_minutes"]
    return cfg


def jsonl_append(path, obj) -> None:
    """Append ``obj`` as a single JSON line.

    The line is written with one ``write`` call in append mode, so concurrent writers
    do not interleave partial lines in practice. Parent directories are created.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    with open(p, "ab") as f:
        f.write(data)


def jsonl_read(path) -> list:
    """All parseable JSON objects in a JSONL file. Missing file -> []. Corrupt lines are skipped."""
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    with open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out
