"""Assinatura digital A1 de documentos (PAdES via pyHanko) — req. 4-6.

- Assina o PDF do documento com o certificado A1 do usuário.
- Carimbo visível no **rodapé da última folha**; se o rodapé estiver ocupado (ex.: imagem
  cobrindo a página), acrescenta uma **nova última folha** para o carimbo (sem sobrescrever).
- Múltiplas assinaturas: cada uma é uma revisão incremental (preserva as anteriores).
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from io import BytesIO

from fastapi import HTTPException, status
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTFigure, LTImage, LTLine, LTRect, LTTextContainer
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.models import (
    Arquivo,
    ArquivoPapel,
    Assinatura,
    AssinaturaStatus,
    Documento,
    LogAuditoria,
    Usuario,
)
from app.services import certificado_service, storage

FOOTER_BAND = 72.0  # pontos a partir da base da página considerados "rodapé"


# ---------------------------------------------------------------- PDF utilitários
def _gerar_pdf_base(doc: Documento) -> bytes:
    reg = doc.registro
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, h - 80, "Documento Digitalizado — Cemitério Bonfim")
    c.setFont("Helvetica", 11)
    y = h - 120
    linhas = [
        f"Documento nº {doc.id}",
        f"Contrato: {getattr(reg, 'contrato', None)}   Lote: {getattr(reg, 'lote', None)}",
        f"Tipo de documento: {doc.tipo_doc_id}",
        f"Folha {doc.nr_folha or 1} de {doc.total_folhas or 1}",
    ]
    for ln in linhas:
        c.drawString(60, y, ln)
        y -= 18
    c.showPage()
    c.save()
    return buf.getvalue()


def _footer_ocupado(pdf_bytes: bytes) -> bool:
    try:
        paginas = list(extract_pages(BytesIO(pdf_bytes)))
    except Exception:  # noqa: BLE001 - PDF exótico -> assume ocupado (mais seguro)
        return True
    ult = paginas[-1]
    for el in ult:
        if isinstance(el, (LTTextContainer, LTFigure, LTImage, LTRect, LTLine)):
            x0, y0, x1, y1 = el.bbox
            if y0 < FOOTER_BAND and (y1 - y0) > 1 and (x1 - x0) > 1:
                return True
    return False


def _num_paginas(pdf_bytes: bytes) -> int:
    return len(PdfReader(BytesIO(pdf_bytes)).pages)


def _tamanho_pagina(pdf_bytes: bytes, idx: int) -> tuple[float, float]:
    box = PdfReader(BytesIO(pdf_bytes)).pages[idx].mediabox
    return float(box.width), float(box.height)


def _append_pagina_branca(pdf_bytes: bytes) -> bytes:
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    last = reader.pages[-1].mediabox
    writer.add_blank_page(width=float(last.width), height=float(last.height))
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _box_carimbo(slot: int, altura_pagina: float) -> tuple[float, float, float, float]:
    margem, larg, alt, gap = 40.0, 260.0, 46.0, 8.0
    y = 24.0 + slot * (alt + gap)
    if y + alt > altura_pagina - 10:
        y = max(10.0, altura_pagina - 10 - alt)
    return (margem, y, margem + larg, y + alt)


def _assinar_pdf(
    base: bytes, pfx: bytes, senha: str, field_name: str, page_idx: int,
    box: tuple[float, float, float, float],
) -> bytes:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigFieldSpec, SigSeedSubFilter, append_signature_field
    from pyhanko.stamp import TextStampStyle

    tmp = tempfile.NamedTemporaryFile(suffix=".pfx", delete=False)
    try:
        tmp.write(pfx)
        tmp.close()
        signer = signers.SimpleSigner.load_pkcs12(pfx_file=tmp.name, passphrase=senha.encode())
    finally:
        os.unlink(tmp.name)
    if signer is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Falha ao carregar o certificado")

    writer = IncrementalPdfFileWriter(BytesIO(base))
    append_signature_field(
        writer, SigFieldSpec(sig_field_name=field_name, on_page=page_idx, box=box)
    )
    meta = signers.PdfSignatureMetadata(
        field_name=field_name,
        subfilter=SigSeedSubFilter.PADES,
        reason="Assinatura eletrônica de documento",
    )
    pdf_signer = signers.PdfSigner(
        meta,
        signer=signer,
        stamp_style=TextStampStyle(stamp_text="Assinado por:\n%(signer)s\nEm %(ts)s"),
    )
    resultado = pdf_signer.sign_pdf(writer)
    return resultado.getvalue() if hasattr(resultado, "getvalue") else resultado.read()


def contar_assinaturas_pdf(pdf_bytes: bytes) -> int:
    from pyhanko.pdf_utils.reader import PdfFileReader

    return len(PdfFileReader(BytesIO(pdf_bytes)).embedded_signatures)


# --------------------------------------------------------------------- serviço
def _obter_base(db: Session, doc: Documento) -> bytes:
    ult = db.scalar(
        select(Assinatura)
        .where(Assinatura.documento_id == doc.id)
        .order_by(Assinatura.ordem.desc())
        .limit(1)
    )
    if ult and ult.arquivo_assinado_id:
        return storage.ler(db, db.get(Arquivo, ult.arquivo_assinado_id))

    full = db.scalar(
        select(Arquivo)
        .where(Arquivo.documento_id == doc.id, Arquivo.papel == ArquivoPapel.full)
        .order_by(Arquivo.id.desc())
        .limit(1)
    )
    if full and ((full.mime or "") == "application/pdf" or (full.extensao or "") == "pdf"):
        return storage.ler(db, full)

    pdf = _gerar_pdf_base(doc)
    storage.guardar(db, ArquivoPapel.full, pdf, documento_id=doc.id, extensao="pdf",
                    mime="application/pdf")
    return pdf


def assinar_documento(
    db: Session, usuario: Usuario, documento_id: int, certificado_id: int
) -> Assinatura:
    doc = db.get(Documento, documento_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    cert = certificado_service.obter_certificado(db, usuario, certificado_id)
    if cert.validade_fim and cert.validade_fim < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_409_CONFLICT, "Certificado expirado")

    pfx, senha = certificado_service.carregar_pfx(db, cert)
    existentes = list(
        db.scalars(
            select(Assinatura).where(Assinatura.documento_id == doc.id).order_by(Assinatura.ordem)
        )
    )
    ordem = len(existentes) + 1
    base = _obter_base(db, doc)

    if ordem == 1:
        nova_folha = _footer_ocupado(base)
        if nova_folha:
            base = _append_pagina_branca(base)  # base ainda sem assinatura: reescrita é segura
        page_idx = _num_paginas(base) - 1
        slot = 0
    else:
        page_idx = existentes[0].carimbo_pagina if existentes[0].carimbo_pagina is not None else _num_paginas(base) - 1
        nova_folha = False
        slot = ordem - 1

    _, altura = _tamanho_pagina(base, page_idx)
    box = _box_carimbo(slot, altura)
    assinado = _assinar_pdf(base, pfx, senha, f"Assinatura_{ordem}", page_idx, box)

    arquivo = storage.guardar(
        db, ArquivoPapel.assinado, assinado, documento_id=doc.id, extensao="pdf",
        mime="application/pdf", created_by=usuario.id,
    )
    assinatura = Assinatura(
        documento_id=doc.id,
        usuario_id=usuario.id,
        certificado_id=cert.id,
        ordem=ordem,
        hash_documento=security.sha256_hex(assinado),
        arquivo_assinado_id=arquivo.id,
        carimbo_pagina=page_idx,
        carimbo_nova_folha=nova_folha,
        carimbo_posicao={"box": list(box), "page": page_idx},
        status=AssinaturaStatus.valida,
        detalhe_cadeia={
            "titular": cert.nome_titular,
            "serie": cert.numero_serie,
            "emissor": cert.emissor,
            "subfilter": "PADES",
        },
    )
    db.add(assinatura)
    db.add(
        LogAuditoria(
            usuario_id=usuario.id,
            acao="documento_assinado",
            entidade="documento",
            entidade_id=doc.id,
            detalhe={"ordem": ordem, "nova_folha": nova_folha},
        )
    )
    db.commit()
    db.refresh(assinatura)
    return assinatura


def listar_assinaturas(db: Session, documento_id: int) -> dict:
    if db.get(Documento, documento_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado")
    itens = list(
        db.scalars(
            select(Assinatura).where(Assinatura.documento_id == documento_id).order_by(Assinatura.ordem)
        )
    )
    no_pdf = None
    if itens and itens[-1].arquivo_assinado_id:
        no_pdf = contar_assinaturas_pdf(storage.ler(db, db.get(Arquivo, itens[-1].arquivo_assinado_id)))
    return {
        "documento_id": documento_id,
        "qtde_assinaturas": len(itens),
        "assinaturas_no_pdf": no_pdf,
        "assinaturas": [
            {
                "ordem": a.ordem,
                "usuario_id": a.usuario_id,
                "assinado_em": a.assinado_em,
                "titular": (a.detalhe_cadeia or {}).get("titular"),
                "carimbo_nova_folha": a.carimbo_nova_folha,
                "carimbo_pagina": a.carimbo_pagina,
                "status": a.status,
                "hash_documento": a.hash_documento,
            }
            for a in itens
        ],
    }


def pdf_assinado(db: Session, documento_id: int) -> bytes:
    ult = db.scalar(
        select(Assinatura)
        .where(Assinatura.documento_id == documento_id)
        .order_by(Assinatura.ordem.desc())
        .limit(1)
    )
    if ult is None or ult.arquivo_assinado_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não possui versão assinada")
    return storage.ler(db, db.get(Arquivo, ult.arquivo_assinado_id))
