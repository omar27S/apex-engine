"""THE HONEST TICK-VALUE ENGINE.

Pure, computed pip value per standard lot. Contract size is 100 000 units and
the account currency is USD (stated, not assumed).

``usd_rates`` maps a *quote currency code* (e.g. ``"GBP"``, ``"JPY"``) to the
number of USD that one unit of that currency is worth. To build it from pair
prices: if the currency is USD-quoted (``GBPUSD``) use that pair's price
directly (1 GBP = 1.27 USD); if it is USD-base (``USDJPY``) use the reciprocal
of that pair's price (1 JPY = 1/150 USD).

Fail-closed: any missing or unusable rate returns ``None``; the caller MUST
reject. There is no fixed rate table and no magic default anywhere in this file.
"""

from __future__ import annotations

from typing import Mapping

from app.core.law import normalize_pair
from app.core.pairs import pip_size

CONTRACT_SIZE = 100_000.0
ACCOUNT_CURRENCY = "USD"


def _usd_rate(currency: str, usd_rates: Mapping[str, float]) -> float | None:
    """Return USD per one unit of ``currency``, or ``None`` if unavailable."""
    if usd_rates is None:
        return None
    rate = usd_rates.get(currency)
    if rate is None or rate <= 0:
        return None
    return rate


def pip_value_per_lot(
    pair: str, price: float, usd_rates: Mapping[str, float]
) -> float | None:
    """Pip value per standard lot in USD, or ``None`` when it cannot be known.

    ``pair`` is canonicalized via the Law; ``price`` is the pair's current
    quote. ``None`` is a hard signal to the caller to reject the trade.
    """
    canonical = normalize_pair(pair)
    if canonical is None:
        return None

    pip = pip_size(canonical)
    if pip is None:
        return None

    if price is None or price <= 0:
        return None

    base, quote = canonical[:3], canonical[3:]

    # XXXUSD: quote is USD -> value is exact, no rate needed.
    if quote == ACCOUNT_CURRENCY:
        return CONTRACT_SIZE * pip

    # USDXXX: base is USD -> convert the quote currency back to USD via price.
    if base == ACCOUNT_CURRENCY:
        return CONTRACT_SIZE * pip / price

    # XXXYYY cross: convert the quote currency to USD.
    rate = _usd_rate(quote, usd_rates)
    if rate is None:
        return None
    return CONTRACT_SIZE * pip * rate
