"""Gold price ORM models — XAU/USD and Au99.99."""

from datetime import date
from sqlalchemy import Date, Float, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GoldPriceXauUsd(Base):
    """International gold price in USD per ounce (XAU/USD)."""

    __tablename__ = "gold_prices_xau_usd"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(50), default="yfinance")

    __table_args__ = (
        Index("idx_xau_date", "trade_date"),
    )


class GoldPriceAu9999(Base):
    """Shanghai Gold Exchange Au99.99 price in CNY per gram."""

    __tablename__ = "gold_prices_au9999"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(50), default="akshare")

    __table_args__ = (
        Index("idx_au9999_date", "trade_date"),
    )
