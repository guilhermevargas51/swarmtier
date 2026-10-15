#!/usr/bin/env python3
"""Trava de dado pessoal do swarmtier.

Este arquivo e PUBLICO: contem so padroes GENERICOS. Termos pessoais ficam
num arquivo LOCAL fora do repo (nunca versionado):

    env SWARMTIER_PII_BLOCKLIST  ou  ~/.swarmtier/pii-blocklist.txt

Formato do blocklist: um termo por linha, sem diferenciar maiuscula nem
acento ("Arvore" = "árvore"). Linhas com '#' no inicio sao comentarios.
Linhas iniciadas por '!' sao EXCECOES: o trecho e removido da linha antes
da comparacao (ex.: '!usuario/repo' libera a URL do proprio repositorio).

Uso:
    python scripts/pii_scan.py              # self-test + varredura da arvore
    python scripts/pii_scan.py --history    # tambem varre git log -p --all
    python scripts/pii_scan.py --self-test  # so o controle positivo

Saida: arquivo:linha · tipo · trecho mascarado. Exit 1 se achar algo.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SELF_REL = "scripts/pii_scan.py"
# Arquivos que definem/exercitam os proprios padroes genericos: ficam fora
# SO da checagem generica (o blocklist vale para eles tambem).
GENERIC_EXEMPT = {SELF_REL}
ISCA_NAME = "_pii_selftest_isca.tmp.txt"

GENERIC = [
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")),
    ("caminho-home", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s'\"]+", re.I)),
    ("caminho-home", re.compile(r"/Users/[^/\s'\"]+")),
    ("caminho-home", re.compile(r"/home/[^/\s'\"]+")),
    ("pasta-pessoal", re.compile(
        r"[A-Za-z]:[\\/]+(?:Documents and Settings|One" r"Drive|Documentos|Meus Documentos)\b", re.I)),
    ("chave", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}")),
    ("chave", re.compile(r"\bghp_[A-Za-z0-9]{20,}")),
    ("chave", re.compile(r"\bAKIA[0-9A-Z]{12,}")),
    ("chave", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("chave", re.compile(r"\bxox[bp]-[A-Za-z0-9\-]{10,}")),
    ("chave", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}")),
    ("segredo", re.compile(
        r"(?:api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{12,}", re.I)),
    ("cpf", re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")),
    ("telefone", re.compile(r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-\d{4}(?!\d)")),
]
EMAIL_OK = re.compile(r"(?:@users\.noreply\.github\.com|@example\.(?:com|org))$", re.I)
ENV_FILE = re.compile(r"(^|/)\.env(\..+)?$")
ENV_OK = re.compile(r"\.(example|sample|template)$", re.I)


def norm(s: str) -> str:
    """minusculas e sem acento, preservando o comprimento por caractere."""
    out = []
    for ch in s:
        d = "".join(c for c in unicodedata.normalize("NFKD", ch)
                    if not unicodedata.combining(c))
        out.append(d.lower() if len(d) == 1 else ch.lower())
    return "".join(out)


def mask(s: str) -> str:
    s = s.strip()
    if len(s) <= 2:
        return "*" * len(s)
    return s[0] + "*" * (len(s) - 2) + s[-1]


def blocklist_path() -> Path:
    env = os.environ.get("SWARMTIER_PII_BLOCKLIST")
    return Path(env) if env else Path.home() / ".swarmtier" / "pii-blocklist.txt"


def load_blocklist():
    """(termos, excecoes, caminho_ou_None)."""
    p = blocklist_path()
    if not p.is_file():
        return [], [], None
    terms, allow = [], []
    for raw in p.read_text(encoding="utf-8").splitlines():
        t = raw.strip()
        if not t or t.startswith("#"):
            continue
        (allow if t.startswith("!") else terms).append(norm(t.lstrip("!").strip()))
    return terms, allow, p


class Matcher:
    def __init__(self, terms, allow):
        self.allow = [a for a in allow if a]
        self.terms = [
            (t, re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])"))
            for t in terms if t
        ]

    def scan_line(self, line: str, generic: bool):
        """Devolve lista de (tipo, trecho_bruto)."""
        found = []
        if generic:
            for tipo, rx in GENERIC:
                for m in rx.finditer(line):
                    txt = m.group(0)
                    if tipo == "email" and EMAIL_OK.search(txt):
                        continue
                    found.append((tipo, txt))
        if self.terms:
            n = norm(line)
            for a in self.allow:
                n = n.replace(a, " " * len(a))
            for t, rx in self.terms:
                for m in rx.finditer(n):
                    found.append(("termo-pessoal", line[m.start():m.end()]))
        return found


def scan_text(rel: str, text: str, matcher: Matcher):
    generic = rel not in GENERIC_EXEMPT
    res = []
    if generic and ENV_FILE.search(rel) and not ENV_OK.search(rel):
        res.append((rel, 0, "arquivo-env", mask(Path(rel).name)))
    for tipo, txt in matcher.scan_line(rel, generic):  # nome do caminho
        res.append((rel, 0, tipo + "(nome)", mask(txt)))
    for i, line in enumerate(text.splitlines(), 1):
        for tipo, txt in matcher.scan_line(line, generic):
            res.append((rel, i, tipo, mask(txt)))
    return res


def git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout


def tracked_files():
    out = git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    return sorted({f for f in out.split("\0") if f})


def read_text(path: Path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def scan_tree(matcher):
    res = []
    for rel in tracked_files():
        p = REPO / rel
        if not p.is_file():
            continue
        text = read_text(p)
        if text is None:
            continue
        res.extend(scan_text(rel, text, matcher))
    return res


def scan_history(matcher):
    out = git("log", "-p", "--all", "--no-color", "--no-ext-diff", "-U0")
    res, seen = [], set()
    commit, fil, ln = "?", "?", 0
    for line in out.splitlines():
        if line.startswith("commit ") and re.fullmatch(r"commit [0-9a-f]{40}.*", line):
            commit = line.split()[1][:8]
        elif line.startswith("+++ "):
            fil = line[4:].removeprefix("b/")
        elif line.startswith("--- "):
            continue
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            ln = int(m.group(1)) if m else 0
        elif line[:1] in "+-" and line:
            body = line[1:]
            for tipo, txt in matcher.scan_line(body, fil not in GENERIC_EXEMPT):
                key = (fil, tipo, txt)
                if key not in seen:
                    seen.add(key)
                    res.append((f"{commit}:{fil}", ln, tipo, mask(txt)))
            if line[0] == "+":
                ln += 1
    # mensagens de commit/autor tambem vazam
    meta = git("log", "--all", "--format=%H%x09%an <%ae>%x09%s")
    for row in meta.splitlines():
        h, _, rest = row.partition("\t")
        for tipo, txt in matcher.scan_line(rest, True):
            res.append((f"{h[:8]}:<metadados>", 0, tipo, mask(txt)))
    return res


def self_test(matcher, terms) -> bool:
    isca = REPO / ISCA_NAME
    esperado = [
        ("email", "fulano" + "@" + "empresa-falsa.com.br"),
        ("caminho-home", "C:" + "\\Users\\" + "fulano"),
        ("chave", "sk" + "-" + "A1b2C3d4E5f6G7h8I9j0"),
    ]
    if terms:
        esperado.append(("termo-pessoal", terms[0]))
    try:
        isca.write_text("\n".join(f"isca {v}" for _, v in esperado) + "\n",
                        encoding="utf-8")
        res = scan_text(ISCA_NAME, isca.read_text(encoding="utf-8"), matcher)
    finally:
        if isca.exists():
            isca.unlink()
    ok = True
    for i, (tipo, _) in enumerate(esperado, 1):
        if not any(r[1] == i and r[2] == tipo for r in res):
            print(f"SELF-TEST FALHOU: isca '{tipo}' (linha {i}) escapou", file=sys.stderr)
            ok = False
    if ok:
        extra = "" if terms else " (sem blocklist: termo pessoal NAO testado)"
        print(f"self-test ok: {len(esperado)} iscas pegas{extra}")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--history", action="store_true", help="varre git log -p --all")
    ap.add_argument("--self-test", action="store_true", help="so o controle positivo")
    a = ap.parse_args(argv)

    terms, allow, path = load_blocklist()
    if path is None:
        print(f"AVISO: blocklist nao encontrada ({blocklist_path()}); rodando so os genericos.",
              file=sys.stderr)
    matcher = Matcher(terms, allow)

    if not self_test(matcher, terms):
        return 1
    if a.self_test:
        return 0

    res = scan_tree(matcher)
    if a.history:
        res += scan_history(matcher)
    for f, ln, tipo, trecho in res:
        print(f"{f}:{ln} · {tipo} · {trecho}")
    if res:
        print(f"\n{len(res)} achado(s).", file=sys.stderr)
        return 1
    print("limpo: nenhum achado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
