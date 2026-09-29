"""Testes do parser do dump Firebird (executáveis com pytest ou direto)."""
from __future__ import annotations

from etl.fb_parser import _quotes_balanced, _tokenizar_valores, parse_insert


def test_insert_simples() -> None:
    tab, row = parse_insert(
        "INSERT INTO GRUPO_USUARIO (GRUPO_USUARIO, DESCR) VALUES (2, 'Diretoria   ');"
    )
    assert tab == "GRUPO_USUARIO"
    assert row["GRUPO_USUARIO"] == 2
    assert row["DESCR"] == "Diretoria   "


def test_null_e_numeros() -> None:
    _, row = parse_insert(
        "INSERT INTO T (A, B, C, D) VALUES (1, NULL, 3.5, 'x');"
    )
    assert row["A"] == 1 and row["B"] is None and row["C"] == 3.5 and row["D"] == "x"


def test_aspas_escapadas() -> None:
    vals = _tokenizar_valores("'O''Brien', 2")
    assert vals == ["O'Brien", 2]


def test_backslash_literal_em_caminho() -> None:
    _, row = parse_insert(
        r"INSERT INTO RI (IMAGE, N) VALUES ('P:\08142008\FULL\297 19257-1.jpg', 5);"
    )
    assert row["IMAGE"] == r"P:\08142008\FULL\297 19257-1.jpg"
    assert row["N"] == 5


def test_virgula_dentro_de_string() -> None:
    _, row = parse_insert("INSERT INTO T (C) VALUES ('a, b, c');")
    assert row["C"] == "a, b, c"


def test_data_como_string() -> None:
    _, row = parse_insert("INSERT INTO T (D) VALUES ('2008-08-14 14:46:13');")
    assert row["D"] == "2008-08-14 14:46:13"


def test_quotes_balanced() -> None:
    assert _quotes_balanced("VALUES ('abc')")
    assert not _quotes_balanced("VALUES ('abc")
    assert _quotes_balanced("VALUES ('O''Brien')")


def _run() -> None:
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {nome}")
    print("todos os testes do parser passaram")


if __name__ == "__main__":
    _run()
