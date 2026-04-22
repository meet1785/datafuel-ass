from typing import Any, Dict, List, Optional

import logging
from fastapi import FastAPI, HTTPException, Query

from services import analyze_campaigns, get_campaigns_by_label

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Campaign Analysis API", version="1.0.0")

_campaigns_cache: Optional[List[Dict[str, Any]]] = None
_summary_cache: Optional[Dict[str, Any]] = None
_skipped_cache: Optional[List[Dict[str, Any]]] = None


def load_campaign_data() -> None:
    global _campaigns_cache, _summary_cache, _skipped_cache
    if _campaigns_cache is None:
        result = analyze_campaigns()
        _campaigns_cache = result.get("campaigns", [])
        _summary_cache = result.get("summary", {})
        _skipped_cache = result.get("skipped_rows", [])


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy", "service": "Campaign Analysis API"}


@app.get("/analyze")
async def analyze(
    label: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1),
    sort_by: str = Query("ROAS"),
) -> Dict[str, Any]:
    load_campaign_data()
    campaigns = list(_campaigns_cache or [])
    if not campaigns:
        raise HTTPException(status_code=404, detail="No campaign data available")

    if label:
        if label not in {"Scale", "Optimize", "Pause"}:
            raise HTTPException(status_code=400, detail="Invalid label")
        campaigns = get_campaigns_by_label(campaigns, label)

    if sort_by in {"ROAS", "CTR", "CPC", "ACOS", "Conversion_Rate", "Sales", "Spend"}:
        reverse = sort_by not in {"ACOS", "CPC"}
        campaigns = sorted(campaigns, key=lambda c: c.get(sort_by, 0), reverse=reverse)

    if limit:
        campaigns = campaigns[:limit]

    return {
        "campaigns": campaigns,
        "summary": _summary_cache,
        "skipped_rows": _skipped_cache,
        "count": len(campaigns),
    }


@app.get("/summary")
async def summary() -> Dict[str, Any]:
    load_campaign_data()
    if not _summary_cache:
        raise HTTPException(status_code=404, detail="No campaign data available")
    return _summary_cache


@app.get("/campaigns/{campaign_name}")
async def campaign_detail(campaign_name: str) -> Dict[str, Any]:
    load_campaign_data()
    campaigns = _campaigns_cache or []
    match = next((c for c in campaigns if c["Campaign"] == campaign_name), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"campaign": match}


@app.get("/insights")
async def insights() -> Dict[str, Any]:
    load_campaign_data()
    campaigns = _campaigns_cache or []
    if not campaigns:
        raise HTTPException(status_code=404, detail="No campaign data available")

    flagged: List[Dict[str, Any]] = []
    for c in campaigns:
        spend = c.get("Spend", 0.0)
        sales = c.get("Sales", 0.0)
        orders = c.get("Orders", 0.0)
        ctr = c.get("CTR", 0.0)
        acos = c.get("ACOS", 0.0)
        roas = c.get("ROAS", 0.0)
        budget = c.get("Budget", 0.0)

        if acos > 80:
            flagged.append(
                {
                    "campaign_name": c["Campaign"],
                    "issue": "High ACOS - spending too much to generate sales",
                    "metric_value": f"ACOS: {acos:.2f}%",
                    "recommendation": "Check Targeting",
                }
            )

        if ctr < 0.3 and c.get("Impressions", 0) > 0:
            flagged.append(
                {
                    "campaign_name": c["Campaign"],
                    "issue": "Low CTR - ad shown but users are not clicking",
                    "metric_value": f"CTR: {ctr:.2f}%",
                    "recommendation": "Review Creative",
                }
            )

        if spend > 0 and orders == 0:
            flagged.append(
                {
                    "campaign_name": c["Campaign"],
                    "issue": "Spend is positive but conversions are zero",
                    "metric_value": f"Spend: {spend:.2f}, Orders: 0",
                    "recommendation": "Pause",
                }
            )

        if roas == 0 and budget > 0:
            flagged.append(
                {
                    "campaign_name": c["Campaign"],
                    "issue": "ROAS is zero while budget is active",
                    "metric_value": f"ROAS: {roas:.2f}, Budget: {budget:.2f}",
                    "recommendation": "Reduce Budget",
                }
            )

    unique: Dict[str, Dict[str, Any]] = {}
    for item in flagged:
        key = f"{item['campaign_name']}::{item['issue']}"
        unique[key] = item

    pause_spend = sum(c["Spend"] for c in campaigns if c.get("Performance_Label") == "Pause")
    total_spend = sum(c["Spend"] for c in campaigns)

    return {
        "flagged_campaigns": list(unique.values()),
        "total_flagged": len(unique),
        "summary": {
            "estimated_wasted_spend": round(pause_spend, 2),
            "wasted_spend_pct": round((pause_spend / total_spend) * 100, 2) if total_spend > 0 else 0.0,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
