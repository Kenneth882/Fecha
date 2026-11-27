"""What an LLM call costs, from the per-model price table."""

from decimal import Decimal

import pytest

from app.services.llm_prices import UnknownModelError, call_cost_usd


def test_a_call_costs_its_input_and_output_tokens_at_the_models_prices() -> None:
    # Sonnet 5.5: $2 per million input tokens, $10 per million output tokens.
    # 2,000 in is $0.004 and 1,500 out is $0.015.
    assert call_cost_usd("claude-sonnet-5-5", 2_000, 1_500) == Decimal("0.019")


def test_a_model_missing_from_the_price_table_is_an_error_not_a_free_call() -> None:
    # Costing it at $0 would let it run past the daily cap unseen.
    with pytest.raises(UnknownModelError, match="claude-imaginary-9"):
        call_cost_usd("claude-imaginary-9", 2_000, 1_500)
