import asyncio

from services import email_service


def test_password_reset_email_contains_the_link_and_recipient_name():
    subject, plain_text, html = email_service.build_password_reset_email("Ada", "test-token")

    assert subject == "Reset Your Password"
    assert "Ada" in plain_text
    assert "test-token" in plain_text
    assert "test-token" in html


def test_send_email_builds_html_and_pdf_attachment(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr(email_service.aiosmtplib, "send", fake_send)
    asyncio.run(
        email_service.send_email(
            to_email="customer@example.com",
            subject="Invoice INV00001",
            plain_text="Plain body",
            html_content="<strong>HTML body</strong>",
            attachments=[{"filename": "invoice.pdf", "content": b"pdf-bytes"}],
        )
    )

    message = captured["message"]
    assert message["To"] == "customer@example.com"
    assert message["Subject"] == "Invoice INV00001"
    assert any(part.get_filename() == "invoice.pdf" for part in message.walk())
