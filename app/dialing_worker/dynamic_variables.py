from pydantic import BaseModel, ConfigDict

from app.models.campaign import Campaign
from app.models.contact import Contact


class DynamicVariables(BaseModel):
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    phone_number: str = ""
    campaign_name: str = ""

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_lead(cls, lead: Contact, campaign: Campaign) -> "DynamicVariables":
        base = {
            "first_name": lead.first_name or "",
            "last_name": lead.last_name or "",
            "company": lead.company or "",
            "phone_number": lead.phone_number,
            "campaign_name": campaign.name,
        }
        extras = lead.custom_vars or {}
        return cls(**base, **extras)

    def to_retell_dict(self) -> dict[str, str]:
        return {k: str(v) for k, v in self.model_dump().items()}
