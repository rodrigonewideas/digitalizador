"""Envio de e-mail (OTP de 2FA, confirmação de cadastro, reset de senha).

Em produção usa SMTP (configurado por env). Em desenvolvimento, sem SMTP, o e-mail
é registrado no log (backend "console") — nunca em produção.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("digitalizador.email")


class EmailNaoConfigurado(RuntimeError):
    pass


def enviar_email(para: str, assunto: str, corpo: str) -> None:
    s = get_settings()
    if s.smtp_host:
        msg = EmailMessage()
        msg["From"] = s.smtp_from or (s.smtp_user or "nao-responder@localhost")
        msg["To"] = para
        msg["Subject"] = assunto
        msg.set_content(corpo)
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if s.smtp_user and s.smtp_password:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return

    if not s.is_prod:
        # Backend de desenvolvimento: registra o conteúdo (inclui o código) no log.
        logger.warning("DEV-EMAIL para=%s | %s\n%s", para, assunto, corpo)
        return

    raise EmailNaoConfigurado("SMTP não configurado em ambiente de produção.")
