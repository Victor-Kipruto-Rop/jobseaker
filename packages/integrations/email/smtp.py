from email.message import EmailMessage
import smtplib
from apps.api.app.core.config import get_settings

def configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from_email)

def send_transactional_email(recipient: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not configured():
        if settings.app_env in {"local", "development", "test"}:
            return False
        raise RuntimeError("SMTP delivery is not configured.")
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        server.send_message(message)
    return True
