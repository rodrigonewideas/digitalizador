"""Parser do dump SQL do Firebird (export IBExpert).

O dump é uma sequência de `INSERT INTO TABELA (cols) VALUES (vals);`:
  * strings entre aspas simples, com escape `''` -> `'`;
  * backslash é literal (não é escape);
  * NULL como palavra-chave; números sem aspas; datas como string;
  * encoding ISO-8859-1 (latin-1); quebras CRLF.

Uso:
    for tabela, linha in iter_inserts(caminho):
        # linha é dict {NOME_COLUNA: valor_python}
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_INSERT_RE = re.compile(
    r"^INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*)\)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _quotes_balanced(texto: str) -> bool:
    """True se o nº de aspas simples não-escapadas for par (statement completo)."""
    total = texto.count("'")
    escapadas = texto.count("''")
    return (total - 2 * escapadas) % 2 == 0


def iter_statements(caminho: str | Path) -> Iterator[str]:
    """Itera statements INSERT completos, unindo linhas quando um valor tem quebra."""
    buf = ""
    with open(caminho, encoding="latin-1", newline="") as fh:
        for linha in fh:
            if not buf:
                if not linha.lstrip()[:11].upper().startswith("INSERT INTO"):
                    continue
                buf = linha
            else:
                buf += linha
            s = buf.rstrip()
            if s.endswith(";") and _quotes_balanced(buf):
                yield s
                buf = ""


def _tokenizar_valores(blob: str) -> list[Any]:
    """Divide o miolo do VALUES(...) em valores Python, respeitando aspas."""
    valores: list[Any] = []
    i, n = 0, len(blob)
    while i < n:
        c = blob[i]
        if c.isspace() or c == ",":
            i += 1
            continue
        if c == "'":
            j = i + 1
            partes: list[str] = []
            while j < n:
                if blob[j] == "'":
                    if j + 1 < n and blob[j + 1] == "'":
                        partes.append("'")
                        j += 2
                        continue
                    j += 1
                    break
                partes.append(blob[j])
                j += 1
            valores.append("".join(partes))
            i = j
        else:
            j = i
            while j < n and blob[j] != ",":
                j += 1
            token = blob[i:j].strip()
            i = j
            if token.upper() == "NULL" or token == "":
                valores.append(None)
            else:
                valores.append(_num(token))
    return valores


def _num(token: str) -> Any:
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return token


def parse_insert(stmt: str) -> tuple[str, dict[str, Any]] | None:
    """Converte um statement em (TABELA, {coluna: valor}). None se não casar."""
    m = _INSERT_RE.match(stmt)
    if not m:
        return None
    tabela = m.group(1).upper()
    colunas = [c.strip().upper() for c in m.group(2).split(",")]
    valores = _tokenizar_valores(m.group(3))
    if len(valores) != len(colunas):
        raise ValueError(
            f"{tabela}: {len(colunas)} colunas x {len(valores)} valores\n{stmt[:200]}"
        )
    return tabela, dict(zip(colunas, valores, strict=True))


def iter_inserts(caminho: str | Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Gera (TABELA, {coluna: valor}) para cada INSERT do dump."""
    for stmt in iter_statements(caminho):
        parsed = parse_insert(stmt)
        if parsed is not None:
            yield parsed
