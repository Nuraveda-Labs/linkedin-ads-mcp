"""LinkedIn Ads MCP — FastMCP server exposing LinkedIn Ads tools.

Run:
  $ glitch-grow-linkedin-ad-mcp                     # stdio, default
  $ glitch-grow-linkedin-ad-mcp --transport sse     # SSE on :8000
  $ python -m linkedin_ads_mcp.server               # equivalent to first

Add to Claude Desktop / Cursor / any MCP client by pointing it at the
binary. Required env: LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET,
LINKEDIN_REFRESH_TOKEN. Optional: LINKEDIN_ACCESS_TOKEN (seeded),
LINKEDIN_API_VERSION (default 202604).

If you don't want to apply for LinkedIn Marketing API access yourself,
a hosted app with elevated approval can connect to your account — see README.
your LinkedIn and we hand you a refresh token scoped to your accounts.
See README for details.
"""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastmcp import FastMCP

from linkedin_ads_mcp.client import LinkedInError, request

mcp = FastMCP("glitch-grow-linkedin-ad-mcp")


# ---------- helpers --------------------------------------------------------

def _start_ms() -> int:
    """Now + 60s buffer (LinkedIn rejects past timestamps)."""
    return int((time.time() + 60) * 1000)


def _date_range_param(days: int) -> dict[str, Any]:
    end = date.today()
    start = end - timedelta(days=days)
    return {
        "dateRange": (
            f"(start:(year:{start.year},month:{start.month},day:{start.day}),"
            f"end:(year:{end.year},month:{end.month},day:{end.day}))"
        ),
    }


def _account_urn(account_id: str | int) -> str:
    return f"urn:li:sponsoredAccount:{account_id}"


def _accounts_list_param(account_id: str | int) -> str:
    # URN colons inside List(...) MUST be %3A-encoded per restli rules.
    return f"List({_account_urn(account_id).replace(':', '%3A')})"


# ---------- read tools -----------------------------------------------------

@mcp.tool()
def list_ad_accounts() -> list[dict]:
    """List every LinkedIn ad account the OAuth user has any role on.

    Returns: [{id, urn, name, type, status, currency, serving_statuses}]
    """
    res = request("GET", "/rest/adAccounts", params={"q": "search"})
    return [
        {
            "id":                str(el.get("id", "")),
            "urn":               f"urn:li:sponsoredAccount:{el.get('id')}",
            "name":              el.get("name", ""),
            "type":              el.get("type", ""),
            "status":            el.get("status", ""),
            "currency":          el.get("currency", ""),
            "serving_statuses":  el.get("servingStatuses", []) or [],
        }
        for el in res.get("elements", [])
    ]


@mcp.tool()
def list_account_users(account_id: str) -> list[dict]:
    """List user→role assignments on an ad account."""
    res = request(
        "GET", "/rest/adAccountUsers",
        params={"q": "accounts", "accounts": _account_urn(account_id)},
    )
    return [
        {"user": el.get("user", ""), "role": el.get("role", ""), "account": el.get("account", "")}
        for el in res.get("elements", [])
    ]


@mcp.tool()
def list_campaign_groups(account_id: str) -> list[dict]:
    """List campaign groups on an ad account."""
    res = request(
        "GET", f"/rest/adAccounts/{account_id}/adCampaignGroups",
        params={"q": "search"},
    )
    return [
        {
            "id":           str(el.get("id", "")),
            "name":         el.get("name", ""),
            "status":       el.get("status", ""),
            "total_budget": (el.get("totalBudget") or {}).get("amount", ""),
            "currency":     (el.get("totalBudget") or {}).get("currencyCode", ""),
        }
        for el in res.get("elements", [])
    ]


@mcp.tool()
def list_campaigns(account_id: str) -> list[dict]:
    """List all campaigns on an ad account (no metrics — use get_campaign_analytics)."""
    res = request(
        "GET", f"/rest/adAccounts/{account_id}/adCampaigns",
        params={"q": "search"},
    )
    return [
        {
            "id":           str(el.get("id", "")),
            "name":         el.get("name", ""),
            "status":       el.get("status", ""),
            "type":         el.get("type", ""),
            "format":       el.get("format", ""),
            "objective":    el.get("objectiveType", ""),
            "daily_budget": (el.get("dailyBudget") or {}).get("amount", ""),
            "currency":     (el.get("dailyBudget") or {}).get("currencyCode", ""),
            "campaign_group": el.get("campaignGroup", ""),
        }
        for el in res.get("elements", [])
    ]


@mcp.tool()
def list_creatives(account_id: str) -> list[dict]:
    """List creatives on an ad account."""
    res = request(
        "GET", f"/rest/adAccounts/{account_id}/creatives",
        params={"q": "criteria"},
    )
    return [
        {
            "id":       str(el.get("id", "")),
            "status":   el.get("status", ""),
            "campaign": el.get("campaign", ""),
            "type":     el.get("type", ""),
        }
        for el in res.get("elements", [])
    ]


@mcp.tool()
def get_account_analytics(account_id: str, days: int = 14) -> dict:
    """Account-level totals over the last N days (impressions, clicks, costInUsd, conversions)."""
    res = request(
        "GET", "/rest/adAnalytics",
        params={
            "q": "analytics", "pivot": "ACCOUNT", "timeGranularity": "ALL",
            "accounts": _accounts_list_param(account_id),
            "fields": "impressions,clicks,costInUsd,externalWebsiteConversions",
            **_date_range_param(days),
        },
    )
    el = (res.get("elements") or [{}])[0]
    impressions = int(el.get("impressions", 0) or 0)
    clicks      = int(el.get("clicks", 0) or 0)
    cost        = float(el.get("costInUsd", 0) or 0)
    return {
        "spend_usd":    round(cost, 2),
        "clicks":       clicks,
        "impressions":  impressions,
        "conversions":  int(el.get("externalWebsiteConversions", 0) or 0),
        "ctr":          round((clicks / impressions) if impressions else 0.0, 4),
        "cpc":          round((cost / clicks) if clicks else 0.0, 2),
        "days":         days,
    }


@mcp.tool()
def get_campaign_analytics(account_id: str, days: int = 14) -> list[dict]:
    """Per-campaign metrics over the last N days, sorted by spend desc."""
    res = request(
        "GET", "/rest/adAnalytics",
        params={
            "q": "analytics", "pivot": "CAMPAIGN", "timeGranularity": "ALL",
            "accounts": _accounts_list_param(account_id),
            "fields": "pivotValues,impressions,clicks,costInUsd,externalWebsiteConversions",
            **_date_range_param(days),
        },
    )
    out = []
    for row in res.get("elements", []):
        urns = row.get("pivotValues") or []
        urn = urns[0] if urns else ""
        impressions = int(row.get("impressions", 0) or 0)
        clicks      = int(row.get("clicks", 0) or 0)
        cost        = float(row.get("costInUsd", 0) or 0)
        out.append({
            "campaign_urn":  urn,
            "campaign_id":   urn.rsplit(":", 1)[-1] if urn else "",
            "spend_usd":     round(cost, 2),
            "clicks":        clicks,
            "impressions":   impressions,
            "conversions":   int(row.get("externalWebsiteConversions", 0) or 0),
            "ctr":           round((clicks / impressions) if impressions else 0.0, 4),
            "cpc":           round((cost / clicks) if clicks else 0.0, 2),
        })
    return sorted(out, key=lambda r: r["spend_usd"], reverse=True)


# ---------- write tools ----------------------------------------------------

@mcp.tool()
def create_campaign_group(
    account_id: str,
    name: str,
    total_budget: float = 100.0,
    currency: str = "USD",
    days: int = 30,
    status: str = "DRAFT",
) -> dict:
    """Create a campaign group. Defaults to DRAFT (required precondition for
    creating DRAFT campaigns inside it). Minimum total_budget is $100 USD."""
    start = _start_ms()
    end = start + days * 24 * 3600 * 1000
    body = {
        "account":     _account_urn(account_id),
        "name":        name,
        "status":      status,
        "runSchedule": {"start": start, "end": end},
        "totalBudget": {"currencyCode": currency, "amount": str(total_budget)},
    }
    res = request("POST", f"/rest/adAccounts/{account_id}/adCampaignGroups", json_body=body)
    cg_id = res.get("_id")
    if not cg_id:
        raise LinkedInError(f"campaign-group create returned no id: {res}")
    return {
        "id":  str(cg_id),
        "urn": f"urn:li:sponsoredCampaignGroup:{cg_id}",
        "name": name,
        "status": status,
    }


@mcp.tool()
def create_campaign(
    account_id: str,
    name: str,
    campaign_group_urn: str,
    daily_budget: float = 10.0,
    unit_cost: float = 10.0,
    currency: str = "USD",
    objective: str = "WEBSITE_TRAFFIC",
    cost_type: str = "CPM",
    type_: str = "TEXT_AD",
    locale_country: str = "US",
    locale_language: str = "en",
    location_geo_urn: str = "urn:li:geo:103644278",
    days: int = 30,
    status: str = "DRAFT",
) -> dict:
    """Create a campaign under an existing campaign group.

    Defaults are demo-safe: DRAFT, $10/day, US/en TEXT_AD with WEBSITE_TRAFFIC
    objective, US-only targeting. Caller must supply `campaign_group_urn`
    (use create_campaign_group first). Status must match the parent group:
    DRAFT/DRAFT or ACTIVE+(PAUSED/ACTIVE).
    """
    start = _start_ms()
    end = start + days * 24 * 3600 * 1000
    body = {
        "account":             _account_urn(account_id),
        "campaignGroup":       campaign_group_urn,
        "name":                name,
        "status":              status,
        "type":                type_,
        "objectiveType":       objective,
        "costType":            cost_type,
        "format":              type_,
        "dailyBudget":         {"currencyCode": currency, "amount": str(daily_budget)},
        "unitCost":            {"currencyCode": currency, "amount": str(unit_cost)},
        "runSchedule":         {"start": start, "end": end},
        "locale":              {"country": locale_country, "language": locale_language},
        "audienceExpansionEnabled": False,
        "offsiteDeliveryEnabled":   False,
        "politicalIntent":     "NOT_DECLARED",
        "targetingCriteria": {
            "include": {
                "and": [
                    {"or": {"urn:li:adTargetingFacet:locations": [location_geo_urn]}}
                ]
            }
        },
    }
    res = request("POST", f"/rest/adAccounts/{account_id}/adCampaigns", json_body=body)
    cid = res.get("_id")
    if not cid:
        raise LinkedInError(f"campaign create returned no id: {res}")
    return {
        "id":  str(cid),
        "urn": f"urn:li:sponsoredCampaign:{cid}",
        "name": name,
        "status": status,
        "campaign_group_urn": campaign_group_urn,
    }


@mcp.tool()
def update_campaign_status(account_id: str, campaign_id: str, status: str) -> dict:
    """Flip a campaign's status. Valid: DRAFT, ACTIVE, PAUSED, ARCHIVED."""
    body = {"patch": {"$set": {"status": status}}}
    request("POST", f"/rest/adAccounts/{account_id}/adCampaigns/{campaign_id}", json_body=body)
    return {"id": campaign_id, "new_status": status}


@mcp.tool()
def update_campaign_group_status(account_id: str, group_id: str, status: str) -> dict:
    """Flip a campaign group's status. Valid: DRAFT, ACTIVE, PAUSED, ARCHIVED, CANCELED."""
    body = {"patch": {"$set": {"status": status}}}
    request("POST", f"/rest/adAccounts/{account_id}/adCampaignGroups/{group_id}", json_body=body)
    return {"id": group_id, "new_status": status}


# ---------- entrypoint -----------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn Ads MCP server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
