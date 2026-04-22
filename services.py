from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
import pandas as pd

from utils import compute_acos, compute_ctr, parse_budget

logger = logging.getLogger(__name__)


class CampaignAnalyzer:
    def __init__(self, input_csv_path: str, output_csv_path: str):
        self.input_path = Path(input_csv_path)
        self.output_path = Path(output_csv_path)
        self.raw_df: Optional[pd.DataFrame] = None
        self.enriched_data: List[Dict[str, Any]] = []
        self.skipped_rows: List[Dict[str, str]] = []

    def load_data(self) -> bool:
        try:
            self.raw_df = pd.read_csv(self.input_path)
            return True
        except Exception as exc:
            logger.error("Failed to load CSV: %s", exc)
            return False

    def clean_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            campaign = str(row.get("Campaigns", "")).strip()
            if not campaign:
                raise ValueError("Campaign name missing")

            cleaned = {
                "Campaign": campaign,
                "Budget": parse_budget(row.get("Budget")),
            }

            for field in ["Impressions", "Clicks", "Spend", "Orders", "Sales"]:
                value = row.get(field)
                cleaned[field] = float(value) if pd.notna(value) else 0.0
                if cleaned[field] < 0:
                    raise ValueError(f"Negative value in {field}")

            return cleaned
        except Exception as exc:
            self.skipped_rows.append(
                {
                    "campaign": str(row.get("Campaigns", "Unknown")),
                    "reason": str(exc),
                }
            )
            return None

    def compute_metrics(self, row: Dict[str, Any]) -> Dict[str, Any]:
        spend = row["Spend"]
        clicks = row["Clicks"]
        orders = row["Orders"]
        sales = row["Sales"]
        impressions = row["Impressions"]

        row["CTR"] = compute_ctr(clicks, impressions)
        row["CPC"] = round(spend / clicks, 2) if clicks > 0 else 0.0
        row["Conversion_Rate"] = round((orders / clicks) * 100, 2) if clicks > 0 else 0.0
        row["ROAS"] = round(sales / spend, 4) if spend > 0 else 0.0
        row["ACOS"] = compute_acos(spend, sales)
        row["Performance_Label"] = self.apply_performance_label(row["ROAS"])
        return row

    @staticmethod
    def apply_performance_label(roas: float) -> str:
        if roas > 3:
            return "Scale"
        if roas >= 1:
            return "Optimize"
        return "Pause"

    def process_all_campaigns(self) -> List[Dict[str, Any]]:
        if self.raw_df is None:
            return []

        self.enriched_data = []
        for _, series in self.raw_df.iterrows():
            cleaned = self.clean_row(series.to_dict())
            if cleaned is None:
                continue
            self.enriched_data.append(self.compute_metrics(cleaned))
        return self.enriched_data

    def save_to_csv(self) -> bool:
        if not self.enriched_data:
            return False
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(self.enriched_data).to_csv(self.output_path, index=False)
        return True

    def get_summary_report(self) -> Dict[str, Any]:
        campaigns = self.enriched_data
        if not campaigns:
            return {}

        total_spend = sum(c["Spend"] for c in campaigns)
        total_sales = sum(c["Sales"] for c in campaigns)
        overall_roas = round(total_sales / total_spend, 4) if total_spend > 0 else 0.0

        best = max(campaigns, key=lambda c: c["ROAS"])
        worst = min(campaigns, key=lambda c: c["ROAS"])

        labels = {"Scale": 0, "Optimize": 0, "Pause": 0}
        for c in campaigns:
            labels[c["Performance_Label"]] = labels.get(c["Performance_Label"], 0) + 1

        pause_spend = sum(c["Spend"] for c in campaigns if c["Performance_Label"] == "Pause")

        return {
            "total_spend": round(total_spend, 2),
            "total_sales": round(total_sales, 2),
            "overall_roas": overall_roas,
            "best_campaign": {"name": best["Campaign"], "roas": best["ROAS"]},
            "worst_campaign": {"name": worst["Campaign"], "roas": worst["ROAS"]},
            "label_breakdown": labels,
            "wasted_spend_pct": round((pause_spend / total_spend) * 100, 2) if total_spend > 0 else 0.0,
        }


def analyze_campaigns(
    input_csv_path: str = "data/campaigns.csv",
    output_csv_path: str = "data/campaigns_analyzed.csv",
) -> Dict[str, Any]:
    analyzer = CampaignAnalyzer(input_csv_path=input_csv_path, output_csv_path=output_csv_path)
    if not analyzer.load_data():
        return {"campaigns": [], "summary": {}, "skipped_rows": [{"campaign": "N/A", "reason": "Failed to load data"}]}

    campaigns = analyzer.process_all_campaigns()
    analyzer.save_to_csv()
    summary = analyzer.get_summary_report()
    return {
        "campaigns": campaigns,
        "summary": summary,
        "skipped_rows": analyzer.skipped_rows,
    }


def get_campaigns_by_label(campaigns: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    if label not in {"Scale", "Optimize", "Pause"}:
        raise ValueError("Label must be Scale, Optimize, or Pause")
    return [c for c in campaigns if c.get("Performance_Label") == label]
