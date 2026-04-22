from typing import Any


def parse_budget(budget_str: Any) -> float:
    if budget_str is None:
        raise ValueError("Budget is missing")
    cleaned = str(budget_str).replace("\u20b9", "").strip()
    if not cleaned:
        raise ValueError("Budget is empty")
    return float(cleaned)


def compute_acos(spend: float, sales: float) -> float:
    if sales <= 0:
        return 0.0
    return round((spend / sales) * 100, 2)


def compute_ctr(clicks: float, impressions: float) -> float:
    if impressions <= 0:
        return 0.0
    return round((clicks / impressions) * 100, 2)
