# Changelog — `linkedin-ads-mcp`

Auto-regenerated from `git log` by `/home/support/bin/changelog-regen`,
called before every push by `/home/support/bin/git-sync-all` (cron `*/15 * * * *`).

**Purpose:** traceability. If a push broke something, scan dates + short SHAs
here; then `git show <sha>` to see the diff, `git revert <sha>` to undo.

**Format:** UTC dates, newest first. Each entry: `time — subject (sha) — N files`.
Body text (if present) shown as indented sub-bullets.

---

## 2026-05-16

- **02:48 UTC** — Publish to MCP registry as com.glitchexecutor.grow/glitch-grow-linkedin-ad-mcp v0.1.1 (`da4dce0`) — 4 files
    - Bump to 0.1.1 (PyPI requires version increment for new mcp-name verification)
    - Add mcp-name HTML comment to README for PyPI ownership verification
    - Add server.json with com.glitchexecutor.grow namespace (DNS-verified via grow.glitchexecutor.com TXT)

## 2026-04-29

- **20:53 UTC** — Clarify status: media upload pattern proven in Grow social agent, port to sponsored creatives queued (`1a71d3d`) — 1 file
- **20:50 UTC** — Point links to grow.glitchexecutor.com (Grow product site) (`02c5c8a`) — 1 file
- **20:49 UTC** — Use support@glitchexecutor.com as contact (`3cc4e31`) — 2 files
- **20:46 UTC** — Rebrand to Glitch Grow LinkedIn Ad MCP + document hosted-app path (`b94a4fa`) — 4 files
    - Package name: linkedin-ads-mcp → glitch-grow-linkedin-ad-mcp
    - Console script renamed accordingly (matches PyPI naming)
    - README leads with two onboarding paths:
        1. DIY — apply for your own LinkedIn Marketing API approval
        2. Hosted — connect Glitch Grow's already-approved app to your
           LinkedIn account, skip the application + approval wait
    - Server identifier + module docstring + Claude Desktop config snippet
      updated to match
    The hosted-app path is the new wedge: anyone who hits the LinkedIn
    Marketing API approval delay can use this MCP immediately by
- **20:41 UTC** — Initial release: linkedin-ads-mcp 0.1.0 (`7f488e9`) — 9 files
    MCP server for LinkedIn Marketing API. Read + write campaigns,
    groups, analytics. Handles restli encoding edge cases (literal
    commas in fields=, %3A inside URN values, partial-update header)
    that bite first-time integrators.
    Tools:
      - list_ad_accounts, list_account_users
      - list_campaign_groups, list_campaigns, list_creatives
      - get_account_analytics, get_campaign_analytics
      - create_campaign_group, create_campaign
      - update_campaign_status, update_campaign_group_status
