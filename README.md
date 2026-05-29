<!-- mcp-name: io.github.nuraveda-labs/linkedin-ads-mcp -->

# LinkedIn Ads MCP

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Part of Mesh Pilot](https://img.shields.io/badge/Mesh%20Pilot-OSS%20tooling-7c3aed.svg)](https://meshpilot.app)

**Model Context Protocol (MCP) server for the LinkedIn Marketing API.**
Read campaigns, pull analytics, create campaign groups + campaigns, flip
statuses — all from any MCP client (Claude Desktop, Cursor, Continue, or
your own agent).

There's no official LinkedIn MCP. This fills the gap with a thin,
correctness-first wrapper that handles LinkedIn's quirky restli encoding
rules so you don't have to.

> Maintained by [Nuraveda Lab](https://nuraveda.com) as open-source tooling
> alongside the [Mesh Pilot](https://meshpilot.app) agent suite. MIT licensed.

---

## Why this exists

If you've tried calling LinkedIn's `/rest/adAnalytics` endpoint by hand
you've probably hit walls like:

- Commas in `fields=` get URL-encoded by default HTTP clients → `400 not present in schema`
- URN colons inside `accounts=List(urn:li:sponsoredAccount:NNN)` need to be `%3A` but date-tuple colons must stay literal
- Partial updates need `X-RestLi-Method: PARTIAL_UPDATE` or they get silently ignored
- `runSchedule.start` must be ≥ now-ish, `totalBudget.amount` must be ≥ $100
- New campaigns need `politicalIntent` (LinkedIn's EU political-ad declaration)

This server has all those rules already encoded.

## Install

**From source (works today):**

```bash
git clone https://github.com/Nuraveda-Labs/linkedin-ads-mcp.git
cd linkedin-ads-mcp
uv pip install -e .          # or: pip install -e .
```

> A PyPI release under the name `linkedin-ads-mcp` is planned. The prior
> package name on PyPI is `glitch-grow-linkedin-ad-mcp` (legacy identity).

## OAuth setup

1. Create a LinkedIn app at <https://www.linkedin.com/developers/apps>.
2. On the **Products** tab, request **Advertising API** (auto-approved if
   you have an active Campaign Manager account).
3. Run any OAuth flow that grants the scopes `r_ads`, `rw_ads`,
   `r_ads_reporting` — for example:

   ```
   https://www.linkedin.com/oauth/v2/authorization?response_type=code
     &client_id=$YOUR_CLIENT_ID
     &redirect_uri=$YOUR_REDIRECT_URI
     &scope=r_ads%20rw_ads%20r_ads_reporting
   ```

4. Exchange the code for tokens; save the access + refresh tokens.
5. Copy `.env.example` to `.env` and paste them.

## Run

```bash
# stdio (Claude Desktop, Cursor, Continue, etc.)
linkedin-ads-mcp

# SSE on :8000
linkedin-ads-mcp --transport sse --port 8000
```

### Claude Desktop config

```json
{
  "mcpServers": {
    "linkedin-ads": {
      "command": "linkedin-ads-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "...",
        "LINKEDIN_CLIENT_SECRET": "...",
        "LINKEDIN_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

## Tools

### Read

| Tool | What it does |
|------|--------------|
| `list_ad_accounts()` | Every ad account the OAuth user can access |
| `list_account_users(account_id)` | User → role assignments |
| `list_campaign_groups(account_id)` | Campaign groups + total budgets |
| `list_campaigns(account_id)` | All campaigns + structure (no metrics) |
| `list_creatives(account_id)` | Creative roster |
| `get_account_analytics(account_id, days=14)` | Account-level totals |
| `get_campaign_analytics(account_id, days=14)` | Per-campaign metrics, sorted by spend |

### Write

| Tool | What it does |
|------|--------------|
| `create_campaign_group(account_id, name, total_budget=100, days=30, status="DRAFT")` | Create a group |
| `create_campaign(account_id, name, campaign_group_urn, daily_budget=10, …)` | Create a campaign (defaults to safe DRAFT TEXT_AD) |
| `update_campaign_status(account_id, campaign_id, status)` | DRAFT / ACTIVE / PAUSED / ARCHIVED |
| `update_campaign_group_status(account_id, group_id, status)` | Same set + CANCELED |

All write tools default to `DRAFT` so nothing goes live by accident.
Promote a group → ACTIVE first, then promote campaigns → PAUSED → ACTIVE
in two explicit steps.

## Multi-tenant pattern

LinkedIn has no MCC, but Campaign Manager has equivalent **"Manage
Access"** sharing. To run this MCP across multiple advertisers:

1. Each client adds your OAuth user as `CAMPAIGN_MANAGER` on their ad
   account (Campaign Manager → Account Settings → Manage Access).
2. After they accept, `list_ad_accounts()` returns their account.
3. Pass that `account_id` to any tool call. One OAuth dance, N advertiser
   accounts — same model as the Google Ads MCC pattern.

## Status

Read API + write API for groups + campaigns are battle-tested in
production. Sponsored-creative creation (image/video upload via
`initializeUpload` → bind to `/rest/creatives` → attach to a campaign)
reuses a proven `/rest/documents` + `/rest/posts` upload pattern; porting
it to the sponsored-ad surface is on the roadmap. PRs welcome.

## License

MIT — see [LICENSE](LICENSE).

## About

Built and maintained by [Nuraveda Lab](https://nuraveda.com), open-sourced
as part of the [Mesh Pilot](https://meshpilot.app) growth-tooling suite.
Hardened against real LinkedIn Marketing API behavior in production. If you
hit a restli encoding edge case we missed, open an issue with the offending
URL and we'll codify the fix.
