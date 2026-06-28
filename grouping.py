"""Balanced grouping for Instagram carousel limits."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")
MAX_INSTAGRAM_IMAGES = 10


def balanced_group_sizes(total: int, maximum: int = MAX_INSTAGRAM_IMAGES) -> list[int]:
    """Return balanced group sizes that never exceed ``maximum``."""
    if total < 0:
        raise ValueError("total must be non-negative")
    if total == 0:
        return []
    if maximum <= 0:
        raise ValueError("maximum must be positive")
    group_count = (total + maximum - 1) // maximum
    half = maximum // 2
    if group_count == 2 and total < maximum * 2 and half > 0 and total % half == 0:
        group_count = total // half
    base, remainder = divmod(total, group_count)
    return [base + 1] * remainder + [base] * (group_count - remainder)


def split_balanced(items: Sequence[T], maximum: int = MAX_INSTAGRAM_IMAGES) -> list[list[T]]:
    """Split items into balanced chunks, preserving order."""
    groups: list[list[T]] = []
    start = 0
    for size in balanced_group_sizes(len(items), maximum):
        groups.append(list(items[start : start + size]))
        start += size
    return groups
