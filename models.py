from pydantic import BaseModel, Field


class CampaignModel(BaseModel):
    campaign: str = Field(..., alias="Campaign")
    budget: float = Field(..., alias="Budget")
    impressions: float = Field(..., alias="Impressions")
    clicks: float = Field(..., alias="Clicks")
    spend: float = Field(..., alias="Spend")
    orders: float = Field(..., alias="Orders")
    sales: float = Field(..., alias="Sales")
    ctr: float = Field(..., alias="CTR")
    cpc: float = Field(..., alias="CPC")
    conversion_rate: float = Field(..., alias="Conversion_Rate")
    roas: float = Field(..., alias="ROAS")
    acos: float = Field(..., alias="ACOS")
    performance_label: str = Field(..., alias="Performance_Label")
