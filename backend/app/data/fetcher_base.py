"""Base class and common utilities for data fetchers."""

from abc import ABC, abstractmethod
from datetime import date
import pandas as pd


class BaseFetcher(ABC):
    """Abstract fetcher — all data source fetchers inherit from this."""

    source: str = "base"

    @abstractmethod
    async def fetch(self, start_date: date | None = None, end_date: date | None = None) -> pd.DataFrame:
        """Fetch data from the source. Returns a DataFrame with at least a 'date' and 'close' column."""
        ...

    @abstractmethod
    async def save_to_db(self, df: pd.DataFrame, session) -> int:
        """Save fetched data to database. Returns number of new records inserted."""
        ...
