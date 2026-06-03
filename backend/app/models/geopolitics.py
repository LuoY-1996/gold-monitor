"""Geopolitical event and risk index ORM models."""

from datetime import date
from sqlalchemy import Date, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GeopoliticalEvent(Base):
    """Key geopolitical/macro events affecting gold prices."""

    __tablename__ = "geopolitical_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1=low, 2=medium, 3=high
    direction: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # +1=利多, -1=利空, 0=中性
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="geopolitics")
    # fed / geopolitics / economy / china / market
    risk_regions: Mapped[str | None] = mapped_column(String(200))  # JSON array: ["russia_ukraine","middle_east"]
    source_url: Mapped[str | None] = mapped_column(String(500))


class GeopoliticalRiskIndex(Base):
    """Daily aggregate geopolitical risk score (1-10)."""

    __tablename__ = "geopolitical_risk_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 - 10.0
    event_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    # Active conflict regions count
    active_conflicts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # News sentiment: -1 (all negative) to +1 (all positive), NULL if no data
    news_sentiment: Mapped[float | None] = mapped_column(Float)
    news_headline_count: Mapped[int | None] = mapped_column(Integer)
    # Regional breakdown (JSON): {"russia_ukraine": 3, "middle_east": 3, "us_china": 2}
    regional_scores: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str | None] = mapped_column(String(50), default="computed")
