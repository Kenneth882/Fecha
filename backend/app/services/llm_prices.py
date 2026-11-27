"""What each model's tokens cost, and so what an LLM call cost.

Pure: standard library only. Prices are Anthropic's first-party API rates in US dollars
per million tokens; update the table when they change or a model is added.
"""

from dataclasses import dataclass
from decimal import Decimal

_PER_MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class ModelPrice:
    """US dollars per million input tokens and per million output tokens."""

    input_per_million: Decimal
    output_per_million: Decimal


PRICES: dict[str, ModelPrice] = {
    "claude-sonnet-5-5": ModelPrice(Decimal(2), Decimal(10)),
    "claude-opus-5-5": ModelPrice(Decimal(4), Decimal(20)),
    # Haiku 5.5's rate for prompts up to 100K tokens, far more than a prompt here uses.
    "claude-haiku-5-5": ModelPrice(Decimal("0.10"), Decimal("0.50")),
    "claude-fable-5-2": ModelPrice(Decimal(8), Decimal(40)),
}


class UnknownModelError(ValueError):
    """The model has no price in the table, so a call to it can't be costed."""


def require_price(model: str) -> ModelPrice:
    """`model`'s price. Raises UnknownModelError for a model that isn't in the table:
    costing it at $0 would let its calls run past the daily cap unseen."""
    price = PRICES.get(model)
    if price is None:
        raise UnknownModelError(
            f"no price for model {model!r}; add it to PRICES in {__name__} "
            f"(priced: {', '.join(sorted(PRICES))})"
        )
    return price


def call_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """What a call to `model` with these token counts cost, in US dollars.

    Raises UnknownModelError for a model that isn't in the price table.
    """
    price = require_price(model)
    return (
        input_tokens * price.input_per_million + output_tokens * price.output_per_million
    ) / _PER_MILLION
