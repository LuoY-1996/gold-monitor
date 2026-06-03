"""Pydantic schemas for gold price API responses."""

from datetime import date
from pydantic import BaseModel


class GoldPricePoint(BaseModel):
    """A single daily gold price data point."""
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int | None = None

    class Config:
        from_attributes = True


class GoldPriceResponse(BaseModel):
    """Wrapper for gold price history response."""
    gold_type: str  # "xau_usd" or "au9999"
    count: int
    data: list[GoldPricePoint]


class GoldRealtimeResponse(BaseModel):
    """Real-time (latest) gold price."""
    gold_type: str
    available: bool = True
    trade_date: date | None = None
    close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None


class GoldCompareResponse(BaseModel):
    """Side-by-side comparison of XAU/USD and Au99.99."""
    trade_date: date
    xau_usd_close: float | None = None
    au9999_close: float | None = None


class FetchDataResponse(BaseModel):
    """Response after triggering data fetch."""
    status: str
    results: dict


class FactorPoint(BaseModel):
    """A single factor data point."""
    trade_date: date
    value: float

    class Config:
        from_attributes = True


class FactorResponse(BaseModel):
    """Wrapper for factor history response."""
    factor_type: str
    count: int
    data: list[FactorPoint]
