from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import company, invoice, user
from services.database import Base


class Customer(Base):
    __tablename__ = 'customers'

    __table_args__ = (
        UniqueConstraint(
            "email",
            "company_id",
            name="uq_customers_email_company",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    tax_id: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
    )
    billing_address: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('companies.id', ondelete='cascade'),
        nullable=False,
        index=True,
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

    # relationships
    company: Mapped[company.Company] = relationship(
        back_populates='customers'
    )
    invoices: Mapped[list[invoice.Invoice]] = relationship(
        back_populates='customer'
    )
    creator: Mapped[user.User] = relationship(
        back_populates='created_customers',
        foreign_keys=[created_by],
    )
    updator: Mapped[user.User] = relationship(
        back_populates='updated_customers',
        foreign_keys=[updated_by],
    )
