from __future__ import annotations

from typing import Any

from evidence.campaign import has_buying_campaign, has_selling_campaign
from evidence.campaign_snapshot import CampaignSnapshot


def evaluate_campaigns(
    ctx: Any,
    *,
    snapshot: CampaignSnapshot | None = None,
) -> tuple[bool, bool]:
    """Evaluate buying/selling campaigns using the current or snapshot path."""
    if snapshot is not None:
        return snapshot.has_buying_campaign(), snapshot.has_selling_campaign()

    return has_buying_campaign(ctx), has_selling_campaign(ctx)


__all__ = ["evaluate_campaigns"]
