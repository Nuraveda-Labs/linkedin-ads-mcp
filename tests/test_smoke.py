"""Smoke tests — import + tool registration. No live API calls."""
from __future__ import annotations


def test_import_server():
    from linkedin_ads_mcp import server
    assert server.mcp is not None


def test_tools_registered():
    import asyncio

    from linkedin_ads_mcp.server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "list_ad_accounts", "list_account_users",
        "list_campaign_groups", "list_campaigns", "list_creatives",
        "get_account_analytics", "get_campaign_analytics",
        "create_campaign_group", "create_campaign",
        "update_campaign_status", "update_campaign_group_status",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


def test_qs_encoding():
    from linkedin_ads_mcp.client import _qs
    # restli rules: literal commas in fields, %3A in URN, literal colons in tuples
    qs = _qs({
        "fields": "impressions,clicks",
        "accounts": "List(urn%3Ali%3AsponsoredAccount%3A1)",
        "dateRange": "(start:(year:2026,month:1,day:1),end:(year:2026,month:1,day:31))",
    })
    assert "fields=impressions,clicks" in qs
    assert "List(urn%3Ali%3AsponsoredAccount%3A1)" in qs
    assert "(start:(year:2026,month:1,day:1)" in qs
