from fastapi.testclient import TestClient


def test_customer_tax_and_invoice_workflow(client: TestClient, registered_user: dict[str, str]):
    customer = client.post(
        "/api/customers",
        headers=registered_user,
        json={
            "name": "Jane Customer",
            "email": "jane@example.com",
            "tax_id": "TAX-001",
            "billing_address": "1 Example Road",
        },
    )
    assert customer.status_code == 201, customer.text

    tax = client.post(
        "/api/taxes",
        headers=registered_user,
        json={"name": "GST", "amount": "18.00", "tax_type": "percent"},
    )
    assert tax.status_code == 201, tax.text

    invoice = client.post(
        "/api/invoices",
        headers=registered_user,
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-01-01",
            "due_date": "2026-01-31",
            "invoice_lines": [
                {
                    "description": "Consulting",
                    "quantity": "2.00",
                    "unit_price": "100.00",
                    "tax_ids": [tax.json()["id"]],
                }
            ],
        },
    )
    assert invoice.status_code == 201, invoice.text
    assert invoice.json()["subtotal"] == "200.00"
    assert invoice.json()["tax_total"] == "36.00"
    assert invoice.json()["total"] == "236.00"

    updated = client.patch(
        f"/api/invoices/{invoice.json()['id']}",
        headers=registered_user,
        json={
            "update_invoice_lines": [
                {
                    "id": invoice.json()["invoice_lines"][0]["id"],
                    "quantity": "3.00",
                    "tax_ids": [],
                }
            ],
            "create_invoice_lines": [
                {
                    "description": "Support",
                    "quantity": "1.00",
                    "unit_price": "50.00",
                    "tax_ids": [tax.json()["id"]],
                }
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert len(updated.json()["invoice_lines"]) == 2
    assert updated.json()["subtotal"] == "350.00"
    assert updated.json()["tax_total"] == "9.00"
    assert updated.json()["total"] == "359.00"

    confirmed = client.patch(
        f"/api/services/confirm-invoice/{invoice.json()['id']}",
        headers=registered_user,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"

    summary = client.get("/api/invoices/summary", headers=registered_user)
    assert summary.status_code == 200, summary.text
    assert summary.json()["total_invoices"] == 1
    assert summary.json()["total_amount"] == "359.00"
    by_status = {item["status"]: item for item in summary.json()["by_status"]}
    assert by_status["confirmed"] == {
        "status": "confirmed",
        "invoice_count": 1,
        "total_amount": "359.00",
    }
    assert by_status["draft"]["invoice_count"] == 0


def test_health_check_and_invalid_invoice_dates(client: TestClient, registered_user: dict[str, str]):
    assert client.get("/health").json() == {"status": "healthy"}

    response = client.post(
        "/api/invoices",
        headers=registered_user,
        json={
            "customer_id": 1,
            "issue_date": "2026-02-01",
            "due_date": "2026-01-01",
            "invoice_lines": [],
        },
    )
    assert response.status_code == 422
    assert "Due date must be on or after issue date" in response.text


def test_customer_email_update_checks_the_new_email(client: TestClient, registered_user: dict[str, str]):
    for name, email in (("One", "one@example.com"), ("Two", "two@example.com")):
        response = client.post(
            "/api/customers",
            headers=registered_user,
            json={
                "name": name,
                "email": email,
                "tax_id": name,
                "billing_address": "1 Example Road",
            },
        )
        assert response.status_code == 201

    response = client.patch(
        "/api/customers/2",
        headers=registered_user,
        json={"email": "one@example.com"},
    )
    assert response.status_code == 400
