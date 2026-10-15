"""Swarm splitter: divide material into batches of at most N tokens, one agent per batch.

Small models cost several times more per token once a prompt passes ~100k tokens. This
splits the material into batches of up to ``--max`` tokens (default 60k, leaving room
for the spec, system prompt and what the agent reads or writes) and says how many agents
to dispatch. A file that alone exceeds the limit is cut by line range ("read lines A-B").

Usage:
    python -m core.swarm_split <files, folders or globs> [--max 60000] [--json out.json]

Output: one batch per line ("batch 3 | ~41k | file.md (l.1-900), other.md") plus a total.
Token estimate: characters / chars_per_token (config, default 3.3). Exit 1 if nothing found.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from core.config import load_config

TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".py", ".js", ".ts", ".html", ".csv", ".toml", ".yaml", ".yml"}


def estimate_tokens(text: str, chars_per_token=None) -> int:
    cpt = chars_per_token or load_config()["swarm"]["chars_per_token"]
    return int(len(text) / cpt)


def pieces(path: Path, max_tokens: int, chars_per_token=None) -> list:
    """``[(label, tokens)]``: the whole file, or line ranges if it alone exceeds ``max_tokens``."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    total = estimate_tokens("".join(lines), chars_per_token)
    if total <= max_tokens:
        return [(str(path), total)]
    out, start, acc = [], 0, 0
    for i, ln in enumerate(lines):
        t = estimate_tokens(ln, chars_per_token)
        if acc + t > max_tokens and i > start:
            out.append(("%s (l.%d-%d)" % (path, start + 1, i), acc))
            start, acc = i, 0
        acc += t
    out.append(("%s (l.%d-%d)" % (path, start + 1, len(lines)), acc))
    return out


def pack(items: list, max_tokens: int) -> list:
    """Greedy first-fit packing, largest first. Returns ``[{"items": [...], "tokens": n}]``."""
    batches: list = []
    for label, t in sorted(items, key=lambda x: -x[1]):
        for b in batches:
            if b["tokens"] + t <= max_tokens:
                b["items"].append(label)
                b["tokens"] += t
                break
        else:
            batches.append({"items": [label], "tokens": t})
    return batches


def collect(targets: list) -> list:
    """Expand files, folders (text files only, skipping dot/underscore dirs) and globs."""
    files: list = []
    for target in targets:
        p = Path(target)
        if p.is_file():
            found = [p]
        elif p.is_dir():
            found = sorted(x for x in p.rglob("*")
                           if x.is_file() and x.suffix in TEXT_SUFFIXES
                           and not any(s[:1] in "._" for s in x.relative_to(p).parts))
        else:
            found = [Path(x) for x in sorted(glob.glob(target, recursive=True))]
        files += [x for x in found if x.is_file()]
    return files


def split(targets: list, max_tokens=None) -> list:
    cfg = load_config()["swarm"]
    max_tokens = max_tokens or cfg["max_tokens"]
    items = [pc for f in collect(targets) for pc in pieces(f, max_tokens)]
    return pack(items, max_tokens)


def main(argv=None) -> int:
    cfg = load_config()["swarm"]
    ap = argparse.ArgumentParser(prog="python -m core.swarm_split", description=__doc__.split("\n")[0])
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--max", type=int, default=cfg["max_tokens"])
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if a.max > cfg["hard_cap_tokens"]:
        print("--max above %dk leaves little headroom before the ~100k price tier. Use at most %d."
              % (cfg["hard_cap_tokens"] // 1000, cfg["hard_cap_tokens"]), file=sys.stderr)
        return 2
    batches = split(a.targets, a.max)
    if not batches:
        print("nothing to split: no text files matched", file=sys.stderr)
        return 1
    for n, b in enumerate(batches, 1):
        print("batch %d | ~%dk | %s" % (n, b["tokens"] // 1000, ", ".join(b["items"])))
    total = sum(b["tokens"] for b in batches)
    print("\n%d agent(s) | ~%dk tokens total | max %dk per batch" % (len(batches), total // 1000, a.max // 1000))
    if len(batches) > cfg["max_agents"]:
        print("warning: more than %d agents - split into waves or raise --max (up to %d)."
              % (cfg["max_agents"], cfg["hard_cap_tokens"]))
    if a.json:
        Path(a.json).write_text(json.dumps(batches, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
