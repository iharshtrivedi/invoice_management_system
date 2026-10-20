from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from models.invoice import Invoice
from models.tax import TaxTypeEnum


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.invoice_number}",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="InvoiceTitle",
            parent=styles["Title"],
            fontSize=22,
            leading=26,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#243447"),
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
        )
    )

    styles.add(
        ParagraphStyle(
            name="RightText",
            parent=styles["Normal"],
            alignment=TA_RIGHT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CellText",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
        )
    )

    story = []

    def money(value: Decimal) -> str:
        return f"{value:,.2f}"

    def paragraph(value, style="Normal") -> Paragraph:
        return Paragraph(str(value), styles[style])

    # --------------------------------------------------
    # Company and invoice heading
    # --------------------------------------------------

    company = invoice.company
    company_name = getattr(company, "name", "Company")

    company_details = [
        paragraph(f"<b>{company_name}</b>", "Heading2"),
    ]

    # Include these fields if your Company model defines them.
    for field in ("address", "email", "phone", "tax_id"):
        value = getattr(company, field, None)
        if value:
            company_details.append(
                paragraph(value, "SmallText")
            )

    invoice_heading = [
        paragraph("INVOICE", "InvoiceTitle"),
        paragraph(
            f"<b>Invoice No:</b> {invoice.invoice_number}",
            "RightText",
        ),
        paragraph(
            f"<b>Status:</b> {invoice.status.value.upper()}",
            "RightText",
        ),
        paragraph(
            f"<b>Issue Date:</b> {invoice.issue_date}",
            "RightText",
        ),
        paragraph(
            f"<b>Due Date:</b> {invoice.due_date}",
            "RightText",
        ),
    ]

    heading = Table(
        [[company_details, invoice_heading]],
        colWidths=[85 * mm, 85 * mm],
    )

    heading.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story.extend(
        [
            heading,
            Spacer(1, 12 * mm),
            paragraph("Invoice Details", "Heading2"),
            Spacer(1, 4 * mm),
        ]
    )

    # --------------------------------------------------
    # Invoice lines
    # --------------------------------------------------

    table_data = [
        [
            paragraph("<b>Description</b>", "CellText"),
            paragraph("<b>Taxes</b>", "CellText"),
            paragraph("<b>Qty</b>", "CellText"),
            paragraph("<b>Unit Price</b>", "CellText"),
            paragraph("<b>Subtotal</b>", "CellText"),
            paragraph("<b>Tax</b>", "CellText"),
            paragraph("<b>Total</b>", "CellText"),
        ]
    ]

    for line in invoice.invoice_lines:
        tax_names = []

        for tax in line.taxes:
            if tax.tax_type == TaxTypeEnum.PERCENT:
                tax_names.append(
                    f"{tax.name} ({money(tax.amount)}%)"
                )
            else:
                tax_names.append(
                    f"{tax.name} (fixed {money(tax.amount)})"
                )

        table_data.append(
            [
                paragraph(line.description, "CellText"),
                paragraph(
                    "<br/>".join(tax_names) if tax_names else "—",
                    "CellText",
                ),
                paragraph(money(line.quantity), "CellText"),
                paragraph(money(line.unit_price), "CellText"),
                paragraph(money(line.line_subtotal), "CellText"),
                paragraph(money(line.line_tax_total), "CellText"),
                paragraph(money(line.line_total), "CellText"),
            ]
        )

    invoice_table = Table(
        table_data,
        colWidths=[
            35 * mm,
            32 * mm,
            13 * mm,
            20 * mm,
            22 * mm,
            18 * mm,
            22 * mm,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )

    invoice_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#243447"),
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9DEE5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    story.extend(
        [
            invoice_table,
            Spacer(1, 8 * mm),
        ]
    )

    # --------------------------------------------------
    # Invoice totals
    # --------------------------------------------------

    totals_data = [
        ["Subtotal", money(invoice.subtotal)],
        ["Tax Total", money(invoice.tax_total)],
        ["Grand Total", money(invoice.total)],
    ]

    totals_table = Table(
        totals_data,
        colWidths=[35 * mm, 30 * mm],
        hAlign="RIGHT",
    )

    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 1), "Helvetica"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                (
                    "LINEABOVE",
                    (0, 2),
                    (-1, 2),
                    1,
                    colors.HexColor("#243447"),
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    story.append(
        Table(
            [[None, totals_table]],
            colWidths=[85 * mm, 85 * mm],
        )
    )

    document.build(story)

    buffer.seek(0)
    return buffer.getvalue()
