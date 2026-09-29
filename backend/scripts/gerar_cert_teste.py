"""Gera um certificado A1 (.pfx) AUTOASSINADO para testes/DEV. Não use em produção."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera .pfx autoassinado para testes")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--senha", default="123456")
    ap.add_argument("--cn", default="FULANO DE TAL:12345678900")
    ap.add_argument("--dias", type=int, default=365)
    args = ap.parse_args()

    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, args.cn)])
    agora = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=args.dias))
        .sign(chave, hashes.SHA256())
    )
    dados = pkcs12.serialize_key_and_certificates(
        b"teste", chave, cert, None, BestAvailableEncryption(args.senha.encode())
    )
    with open(args.saida, "wb") as fh:
        fh.write(dados)
    print(f"Gerado {args.saida} (senha: {args.senha})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
