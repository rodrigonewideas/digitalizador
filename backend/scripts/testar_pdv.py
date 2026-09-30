"""Testa a conexão com o banco comercial (Firebird PDV_BONFIM) e o SQL do terreno.

Uso (dentro do container backend, com as variáveis PDV_* no .env):
    docker compose -f docker-compose.prod.yml exec backend \
        python -m scripts.testar_pdv --terreno 1588

Faz apenas SELECTs (somente leitura). Serve para conferir host/credenciais/charset
e ver se o terreno resolve para contratos + cessionários antes de usar na tela.
"""
from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.services.gateway_comercial import DbGateway


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnóstico da integração comercial (PDV Firebird)")
    ap.add_argument("--terreno", default="1588", help="nr_terreno (Nº do lote) para testar")
    args = ap.parse_args()

    s = get_settings()
    print("== Config PDV ==")
    print(f"  host={s.pdv_fb_host}  port={s.pdv_fb_port}  charset={s.pdv_fb_charset}")
    print(f"  database={s.pdv_fb_database}")
    print(f"  user={s.pdv_fb_user}  senha={'***' if s.pdv_fb_password else '(vazia)'}")
    print(f"  habilitado={s.pdv_habilitado}")
    if not s.pdv_habilitado:
        print("\n>> Integração DESLIGADA: preencha PDV_FB_DATABASE/USER/PASSWORD no .env.")
        return 2

    gw = DbGateway(s)

    print("\n== Conexão / versão do servidor ==")
    try:
        import firebirdsql

        with firebirdsql.connect(
            host=s.pdv_fb_host, port=s.pdv_fb_port, database=s.pdv_fb_database,
            user=s.pdv_fb_user, password=s.pdv_fb_password, charset=s.pdv_fb_charset,
        ) as con:
            cur = con.cursor()
            cur.execute("select rdb$get_context('SYSTEM','ENGINE_VERSION') from rdb$database")
            print(f"  OK — Firebird engine: {cur.fetchone()[0]}")
    except Exception as e:  # noqa: BLE001
        print(f"  FALHOU: {type(e).__name__}: {e}")
        print("  -> confira rede (Bonfim->192.168.5.232:3050), caminho do .gdb, usuário/senha e charset.")
        return 1

    print(f"\n== Terreno {args.terreno!r} -> contratos ==")
    contratos = gw.contratos_por_terreno(args.terreno)
    print(f"  contratos encontrados: {contratos or '(nenhum)'}")

    if contratos:
        print("\n== Cessionários por contrato ==")
        infos = gw.resolver_contratos(contratos)
        for cid in contratos:
            info = infos.get(cid)
            if info:
                print(f"  contrato {cid} | nr_contrato={info.nr_contrato} | terreno={info.nr_terreno} "
                      f"| tipo={info.tipo_terreno}")
                for nome in info.cessionarios or []:
                    print(f"      - {nome}")
            else:
                print(f"  contrato {cid} | (sem dados comerciais)")
    print("\nConcluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
