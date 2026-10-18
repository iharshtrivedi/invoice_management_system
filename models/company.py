from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import customer, invoice, tax, user
from services.database import Base


class Company(Base):
    __tablename__ = 'companies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    gstin: Mapped[str | None] = mapped_column(
        String(15),
        nullable=True,
        default=None,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default='INR',
    )
    invoice_prefix: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default='INV',
    )
    invoice_next_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Relations
    users: Mapped[list[user.User]] = relationship(
        back_populates='company',
        cascade='all, delete-orphan',
    )
    customers: Mapped[list[customer.Customer]] = relationship(
        back_populates='company',
        cascade='all, delete-orphan',
    )
    invoices: Mapped[list[invoice.Invoice]] = relationship(
        back_populates='company',
        cascade='all, delete-orphan',
    )
    taxes: Mapped[list[tax.Tax]] = relationship(
        back_populates='company',
        cascade='all, delete-orphan',
    )
