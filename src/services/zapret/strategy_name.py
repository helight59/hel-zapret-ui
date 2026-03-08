from __future__ import annotations

import re


def normalize_strategy_key(value: str) -> str:
    strategy = (value or '').strip().strip('"').replace('/', '\\').casefold()
    if strategy.endswith('.bat'):
        strategy = strategy[:-4]
    return strategy


def normalize_strategy_name(value: str) -> str:
    strategy = (value or '').strip()
    if strategy.casefold().endswith('.bat'):
        strategy = strategy[:-4]
    return re.sub(r'\s+', ' ', strategy).strip()
