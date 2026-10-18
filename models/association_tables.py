from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table

from services.database import Base

invoice_line_tax = Table(
    'invoice_line_tax',
    Base.metadata,
    Column(
        'invoice_line_id',
        ForeignKey('invoice_lines.id', ondelete='CASCADE'),
        primary_key=True,
    ),
    Column(
        'tax_id',
        ForeignKey('taxes.id'),
        primary_key=True,
    ),
)
