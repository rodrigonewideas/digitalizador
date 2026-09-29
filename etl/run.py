"""CLI do ETL: parseia o dump Firebird e carrega no PostgreSQL.

Exemplos:
    # carga completa
    DATABASE_URL=postgresql://user:pass@host:5432/db \
        python -m etl.run --dump /data/digitalizador_dados

    # teste rápido (limita imagens)
    python -m etl.run --dump /data/digitalizador_dados --max-images 5000
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg

from etl.migrate import Migrator


def _normalizar_url(url: str) -> str:
    # aceita URLs no formato SQLAlchemy (postgresql+psycopg://) e converte p/ libpq
    return url.replace("+psycopg", "").replace("+asyncpg", "").replace("+psycopg2", "")


def _tabela_relatorio(migr: Migrator) -> str:
    origem = migr.report["origem"]
    carregado = migr.report["carregado"]
    pulado = migr.report["pulado"]
    nulif = migr.report["fk_nulificada"]
    linhas = ["", "== Conciliação =="]
    linhas.append(f"{'tabela (origem)':28} {'origem':>10} {'carregado':>10} {'pulado':>8} {'fk_null':>8}")
    mapa = {
        "GRUPO_USUARIO": "grupo", "TIPO_DOC": "tipo_documento",
        "TIPO_DOC_NITI": "tipo_documento_pagina", "GRUPO_TIPODOC": "grupo_tipo_documento",
        "INDICE_ORIGINAL": "indice_original", "INDICE_APOS_1999": "indice_apos_1999",
        "MOTIVO": "motivo", "HD": "volume_storage", "PARAM": "parametro", "USUARIO": "usuario",
        "PARAM_USUARIO": "parametro_usuario", "REGISTRO": "registro",
        "REGISTRO_IMAGE": "documento", "REGISTRO_REFUGO": "refugo",
    }
    for src, dst in mapa.items():
        linhas.append(
            f"{src:28} {origem.get(src, 0):>10} {carregado.get(dst, 0):>10} "
            f"{pulado.get(dst, 0):>8} {nulif.get(dst, 0):>8}"
        )
    if carregado.get("documento_legado"):
        linhas.append(f"{'  (documento_legado)':28} {'':>10} {carregado['documento_legado']:>10}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ETL Firebird -> PostgreSQL")
    parser.add_argument("--dump", required=True, help="caminho do arquivo digitalizador_dados")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--work-dir", default="etl/_work", help="onde ficam os .jsonl intermediários")
    parser.add_argument("--max-images", type=int, default=0, help="limita REGISTRO_IMAGE (0 = todas)")
    parser.add_argument("--skip-parse", action="store_true", help="reaproveita os .jsonl existentes")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("ERRO: informe --database-url ou a variável DATABASE_URL", file=sys.stderr)
        return 2

    conn = psycopg.connect(_normalizar_url(args.database_url))
    migr = Migrator(conn, Path(args.work_dir), max_images=args.max_images)

    t0 = time.monotonic()
    if not args.skip_parse:
        print(f"Parseando dump: {args.dump} ...", flush=True)
        migr.parse_dump(args.dump)
        print(f"  tabelas parseadas: {migr.report['origem']}", flush=True)
    print("Carregando no PostgreSQL ...", flush=True)
    migr.load_all()
    conn.close()

    print(_tabela_relatorio(migr))
    print(f"\nConcluído em {time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
