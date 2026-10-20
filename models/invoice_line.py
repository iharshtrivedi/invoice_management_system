from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import invoice, tax, user
from models.association_tables import invoice_line_tax
from services.database import Base


class InvoiceLine(Base):
    __tablename__ = 'invoice_lines'

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    invoice_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('invoices.id', ondelete='CASCADE'),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    line_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    line_tax_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id'),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id'),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # relations
    invoice: Mapped[invoice.Invoice] = relationship(
        back_populates='invoice_lines',
    )
    taxes: Mapped[list[tax.Tax]] = relationship(
        secondary=invoice_line_tax,
        back_populates='invoice_lines',
    )
    creator: Mapped[user.User] = relationship(
        back_populates='created_invoice_lines',
        foreign_keys=[created_by],
    )
    updator: Mapped[user.User] = relationship(
        back_populates='updated_invoice_lines',
        foreign_keys=[updated_by],
    )
