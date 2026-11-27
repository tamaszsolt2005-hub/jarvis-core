"""Shared, deterministic scoring primitives used by JARVIS scoring domains."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def calculate_weighted_score(
    scores: Mapping[str, Any],
    weights: Mapping[str, float],
    *,
    reverse_scored: Sequence[str] = (),
    precision: int = 2,
) -> float | None:
    """Calculate a validated 0-100 weighted score; None means incomplete input."""
    if not isinstance(scores, Mapping) or not isinstance(weights, Mapping) or not weights:
        raise ValueError("scores and non-empty weights mappings are required")
    if any(not isinstance(key, str) or not key for key in weights):
        raise ValueError("score dimension names must be non-empty strings")
    if any(isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0 for w in weights.values()):
        raise ValueError("weights must be non-negative numbers")
    if abs(sum(float(w) for w in weights.values()) - 1.0) > 1e-9:
        raise ValueError("weights must sum to 1")
    if any(key not in weights for key in reverse_scored):
        raise ValueError("reverse_scored contains an unknown dimension")
    if any(key not in scores or scores[key] is None for key in weights):
        return None
    total = 0.0
    for key, weight in weights.items():
        value = scores[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be a number between 0 and 100")
        normalized = 100.0 - float(value) if key in reverse_scored else float(value)
        total += normalized * float(weight)
    if isinstance(precision, bool) or not isinstance(precision, int) or precision < 0:
        raise ValueError("precision must be a non-negative integer")
    return round(total, precision)
