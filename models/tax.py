from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import enum

from sqlalchemy import Enum as SQLAlchemyEnum, Numeric, func
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models import company, invoice_line, user
from models.association_tables import invoice_line_tax
from services.database import Base


class TaxTypeEnum(str, enum.Enum):
    PERCENT = 'percent'
    FIXED = 'fixed'


class Tax(Base):
    __tablename__ = 'taxes'

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal('0.00'),
    )
    tax_type: Mapped[TaxTypeEnum] = mapped_column(
        SQLAlchemyEnum(
            TaxTypeEnum,
            name='tax_type_enum',
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
        default=TaxTypeEnum.PERCENT,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('companies.id', ondelete='CASCADE'),
        nullable=False,
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

    invoice_lines: Mapped[list[invoice_line.InvoiceLine]] = relationship(
        secondary=invoice_line_tax,
        back_populates='taxes',
    )
    companies: Mapped[company.Company] = relationship(
        back_populates='taxes',
    )
    user: Mapped[user.User] = relationship(
        back_populates='customers',
    )
