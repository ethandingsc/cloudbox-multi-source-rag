---
title: What's New in CloudBox 2.1
slug: whats-new-21
source_type: blog
version: 2.1
date: 2024-05-06
author: Release Team
topics: release, 2fa, teams
---

# What's New in CloudBox 2.1

## Mandatory 2FA for Organizations

Starting with 2.1, two-factor authentication is required for every organization account — admins no longer get to choose. Members have a 14-day grace period to enroll a TOTP authenticator app, after which un-enrolled accounts are locked until enrollment. Personal accounts are unaffected: 2FA remains optional there. This is the single most requested security feature from our Enterprise customers, and we expect it to eliminate the majority of account-takeover tickets.

## New Team Folder Controls

Team folders now support granular roles with per-folder overrides: an admin can grant a contractor edit access to exactly one project folder instead of the whole org. Leaving members are handled automatically — when an account is deactivated, their team folder access is revoked immediately and their personal files transfer to an admin-designated account. No more orphaned files.

## Faster Sync Engine

The delta sync engine got a 40% throughput improvement for folders with many small files, which is exactly the pattern teams hit every day. First sync of a large team folder also completes faster thanks to improved parallel block transfers. There's nothing to configure — clients update automatically over the following weeks.

## Upgrade Notes

The 2.1 rollout is automatic and staged; if your org hasn't been upgraded yet, you'll see a notice in the admin console with your scheduled date. The API is unchanged and no integrations need updates. One reminder: the 2FA requirement starts the moment your org upgrades, so tell your team to enroll their authenticators now rather than on deadline day.
