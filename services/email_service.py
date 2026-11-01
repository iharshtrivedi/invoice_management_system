from email.message import EmailMessage
import base64

import aiosmtplib
from fastapi.templating import Jinja2Templates

from config import settings
templates = Jinja2Templates(directory="templates")


async def send_email(
    to_email: str,
    subject: str,
    plain_text: str,
    html_content: str | None = None,
    attachments: list[dict] | None = None,
) -> None:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject

    message.set_content(plain_text)

    if html_content:
        message.add_alternative(html_content, subtype="html")

    for attachment in attachments or []:
        content = attachment["content"]
        if isinstance(content, str):
            content = base64.b64decode(content)
        message.add_attachment(
            content,
            maintype="application",
            subtype="pdf",
            filename=attachment["filename"],
        )

    await aiosmtplib.send(
        message,
        hostname=settings.mail_server,
        port=settings.mail_port,
        username=settings.mail_username or None,
        password=settings.mail_password.get_secret_value() or None,
        start_tls=settings.mail_use_tls,
    )


def build_password_reset_email(
    username: str,
    token: str,
) -> tuple[str, str, str]:
    """Return the subject and bodies to enqueue through the email worker."""
    reset_url = f"{settings.frontend_url}/reset-password?token={token}"

    template = templates.env.get_template("email/password_reset.html")
    html_content = template.render(reset_url=reset_url, username=username)

    plain_text = f"""Hi {username},

You requested to reset your password. Click the link below to set a new password:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.

Best regards,
The Invoice Management System Team
"""

    return "Reset Your Password", plain_text, html_content
