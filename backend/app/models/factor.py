"""Influencing factor ORM models — DXY, VIX, Treasury yields, CPI."""

from datetime import date
from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FactorDxy(Base):
    """US Dollar Index."""

    __tablename__ = "factor_dxy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), default="yfinance")


class FactorVix(Base):
    """CBOE Volatility Index (VIX)."""

    __tablename__ = "factor_vix"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), default="yfinance")


class FactorTreasury10y(Base):
    """US 10-Year Treasury Yield (in percent, e.g. 4.25 for 4.25%)."""

    __tablename__ = "factor_treasury_10y"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    yield_value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), default="yfinance")


class FactorCpi(Base):
    """US Consumer Price Index (monthly)."""

    __tablename__ = "factor_cpi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    cpi_value: Mapped[float] = mapped_column(Float, nullable=False)
    cpi_yoy_pct: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(50), default="fredapi")


class FactorOil(Base):
    """Crude oil price — Brent (WTI fallback)."""

    __tablename__ = "factor_oil"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), default="sina")


class FactorUsdCny(Base):
    """USD/CNY exchange rate (onshore & offshore)."""

    __tablename__ = "factor_usd_cny"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(50), default="akshare")
