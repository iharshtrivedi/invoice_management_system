from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import company, invoice_line, user
from services.database import Base


class StatusEnum(str, enum.Enum):
    DRAFT = 'draft'
    CONFIRMED = 'confirmed'
    SENT = 'sent'
    PAID = 'paid'
    CANCELLED = 'cancelled'


class Invoice(Base):
    __tablename__ = 'invoices'

    __table_args__ = (
        UniqueConstraint(
            'invoice_number',
            'company_id',
            name='uq_invoice_number_company',
        ),
        CheckConstraint(
            'due_date >= issue_date',
            name='ck_invoice_due_date_gte_issue_date',
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    status: Mapped[StatusEnum] = mapped_column(
        SQLAlchemyEnum(
            StatusEnum,
            name='status_enum',
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=StatusEnum.DRAFT,
    )
    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    email_sent_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
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
    company: Mapped[company.Company] = relationship(
        back_populates='invoices',
    )
    user: Mapped[user.User] = relationship(
        back_populates='invoices',
    )
    invoice_lines: Mapped[list[invoice_line.InvoiceLine]] = relationship(
        back_populates='invoice',
        cascade='all, delete-orphan',
    )
