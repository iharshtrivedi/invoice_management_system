import hashlib
import hmac
import json

from fastapi.testclient import TestClient


WEBHOOK_SECRET = b"test-payment-webhook-secret"


def _signed_payload(payload: dict) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(WEBHOOK_SECRET, body, hashlib.sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-Payment-Signature": f"sha256={signature}",
    }


def _create_invoice(client: TestClient, headers: dict[str, str]) -> int:
    customer = client.post(
        "/api/customers",
        headers=headers,
        json={
            "name": "Webhook Customer",
            "email": "webhook-customer@example.com",
            "tax_id": "WEBHOOK-001",
            "billing_address": "1 Example Road",
        },
    )
    assert customer.status_code == 201, customer.text

    invoice = client.post(
        "/api/invoices",
        headers=headers,
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "invoice_lines": [
                {
                    "description": "Webhook test service",
                    "quantity": "1.00",
                    "unit_price": "100.00",
                    "tax_ids": [],
                }
            ],
        },
    )
    assert invoice.status_code == 201, invoice.text
    return invoice.json()["id"]


def test_payment_webhook_rejects_bad_signatures(client: TestClient):
    response = client.post(
        "/api/webhooks/payment",
        content=b'{"event_id":"evt_bad","invoice_id":1,"payment_status":"paid"}',
        headers={"Content-Type": "application/json", "X-Payment-Signature": "invalid"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_payment_webhook_is_idempotent_and_rejects_unknown_invoices(
    client: TestClient,
    registered_user: dict[str, str],
):
    invoice_id = _create_invoice(client, registered_user)
    payload = {"event_id": "evt_payment_001", "invoice_id": invoice_id, "payment_status": "paid"}
    body, signature_headers = _signed_payload(payload)

    processed = client.post("/api/webhooks/payment", content=body, headers=signature_headers)
    assert processed.status_code == 200, processed.text
    assert processed.json() == {"status": "processed", "event_id": "evt_payment_001"}

    invoice = client.get(f"/api/invoices/{invoice_id}", headers=registered_user)
    assert invoice.status_code == 200
    assert invoice.json()["status"] == "paid"
    assert invoice.json()["paid_at"] is not None

    duplicate = client.post("/api/webhooks/payment", content=body, headers=signature_headers)
    assert duplicate.status_code == 200
    assert duplicate.json() == {"status": "duplicate", "event_id": "evt_payment_001"}

    unknown_body, unknown_headers = _signed_payload(
        {"event_id": "evt_unknown_invoice", "invoice_id": 9999, "payment_status": "paid"}
    )
    unknown_invoice = client.post(
        "/api/webhooks/payment",
        content=unknown_body,
        headers=unknown_headers,
    )
    assert unknown_invoice.status_code == 404
    assert unknown_invoice.json()["detail"] == "Invoice not found"
