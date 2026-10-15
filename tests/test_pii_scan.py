import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "pii_scan.py"
spec = importlib.util.spec_from_file_location("pii_scan", SCRIPT)
pii = importlib.util.module_from_spec(spec)
sys.modules["pii_scan"] = pii
spec.loader.exec_module(pii)


@pytest.fixture
def blocklist(tmp_path, monkeypatch):
    f = tmp_path / "bl.txt"
    f.write_text("# c\n!dono/repo\nÁrvore\nzebra\n", encoding="utf-8")
    monkeypatch.setenv("SWARMTIER_PII_BLOCKLIST", str(f))
    return f


def matcher():
    terms, allow, _ = pii.load_blocklist()
    return pii.Matcher(terms, allow), terms


def tipos(text, m, rel="x.py"):
    return {r[2] for r in pii.scan_text(rel, text, m)}


def test_genericos(monkeypatch, tmp_path):
    monkeypatch.setenv("SWARMTIER_PII_BLOCKLIST", str(tmp_path / "nao-existe"))
    m, _ = matcher()
    assert "email" in tipos("a " + "fulano" + "@" + "foo.com.br", m)
    assert "caminho-home" in tipos("C:" + "\\Users\\" + "fulano\\x", m)
    assert "caminho-home" in tipos("/ho" + "me/fulano/x", m)
    assert "chave" in tipos("sk" + "-" + "A1b2C3d4E5f6G7h8I9", m)
    assert "chave" in tipos("-----BEGIN RSA " + "PRIVATE KEY-----", m)
    assert "segredo" in tipos("api_key = '" + "x" * 14 + "'", m)
    assert "cpf" in tipos("123.456." + "789-09", m)
    assert "telefone" in tipos("(48) 99999" + "-1234", m)
    assert "arquivo-env" in tipos("", m, rel="cfg/.env")


def test_permitidos(monkeypatch, tmp_path):
    monkeypatch.setenv("SWARMTIER_PII_BLOCKLIST", str(tmp_path / "nao-existe"))
    m, _ = matcher()
    assert not tipos("x" + "@" + "users.noreply.github.com", m)
    assert not tipos("x" + "@" + "example.com e y" + "@" + "example.org", m)
    assert not tipos("", m, rel=".env.example")
    assert not tipos("api_key = os.environ['X']", m)


def test_blocklist_sem_acento_e_mascara(blocklist):
    m, _ = matcher()
    r = pii.scan_text("a.md", "Visitei a ARVORE ontem", m)
    assert [(x[1], x[2], x[3]) for x in r] == [(1, "termo-pessoal", "A****E")]
    assert pii.scan_text("a.md", "a Árvore", m)


def test_limite_de_palavra_e_excecao(blocklist):
    m, _ = matcher()
    assert not pii.scan_text("a.md", "ozebra e zebrabyte", m)
    assert not pii.scan_text("a.md", "ver github.com/dono/repo", m)
    assert pii.scan_text("a.md", "ver zebra", m)


def test_blocklist_vale_no_proprio_scanner(blocklist):
    m, _ = matcher()
    assert pii.scan_text(pii.SELF_REL, "zebra", m)
    assert not pii.scan_text(pii.SELF_REL, "sk" + "-" + "A1b2C3d4E5f6G7h8I9", m)


def test_self_test_passa_e_limpa_isca(blocklist):
    m, terms = matcher()
    assert pii.self_test(m, terms)
    assert not (pii.REPO / pii.ISCA_NAME).exists()


def test_self_test_detecta_scanner_cego(blocklist, monkeypatch):
    m, terms = matcher()
    monkeypatch.setattr(pii, "GENERIC", [])
    assert not pii.self_test(m, terms)
    assert not (pii.REPO / pii.ISCA_NAME).exists()
