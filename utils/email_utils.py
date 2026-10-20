from email.message import EmailMessage

import aiosmtplib
from fastapi.templating import Jinja2Templates

from config import settings
from models import invoice as invoice_model

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
        message.add_attachment(
            attachment["content"],
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


async def send_invoice_email(
    to_email: str,
    customer_name: str,
    invoice: invoice_model.Invoice,
    pdf_bytes: bytes,
    invoice_url: str | None = None,
) -> None:
    template = templates.env.get_template(
        "email/send_invoice.html"
    )

    html_content = template.render(
        company_name=invoice.company.name,
        customer_name=customer_name,
        invoice_number=invoice.invoice_number,
        issue_date=invoice.issue_date.strftime("%d %b %Y"),
        due_date=invoice.due_date.strftime("%d %b %Y"),
        currency=invoice.company.currency,
        total=f"{invoice.total:,.2f}",
        status=invoice.status.value,
        invoice_url=invoice_url,
    )

    plain_text = f"""Hi {customer_name},

Please find your invoice details below.

Invoice Number: {invoice.invoice_number}
Invoice Date: {invoice.issue_date:%d %b %Y}
Due Date: {invoice.due_date:%d %b %Y}
Amount: {invoice.company.currency} {invoice.total:,.2f}
Status: {invoice.status.value.upper()}

The invoice PDF is attached to this email.

Thank you for your business!

Best regards,
The Invoice Management System Team
"""

    if invoice_url:
        plain_text += f"\nView Invoice: {invoice_url}\n"

    await send_email(
        to_email=to_email,
        subject=f"Invoice {invoice.invoice_number}",
        plain_text=plain_text,
        html_content=html_content,
        attachments=[
            {
                "filename": f"invoice_{invoice.invoice_number}.pdf",
                "content": pdf_bytes,
            }
        ],
    )


async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
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

    await send_email(
        to_email=to_email,
        subject="Reset Your Password",
        plain_text=plain_text,
        html_content=html_content,
    )
