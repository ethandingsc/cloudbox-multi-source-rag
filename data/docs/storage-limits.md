---
title: Storage Limits
slug: storage-limits
source_type: documentation
version: 2.1
date: 2024-05-12
topics: storage, quota, plans, upload
---

# Storage Limits

## Free Plan Storage

The CloudBox free plan includes **10 GB** of storage, shared across all files you own. This limit applies to the total size of your synced files plus anything you upload through the web app or mobile clients. File versions and recycle bin contents do not count toward your quota. When you approach the limit, CloudBox warns you by email and with an in-app banner; once the quota is reached, syncing pauses until you free space or upgrade. The free plan was raised from 5 GB to 10 GB with CloudBox 2.0 (September 2023). The current limit is 10 GB.

## Paid Plan Tiers

The Plus plan includes **2 TB** of storage for individuals at $9.99 per month. The Business plan includes **10 TB** shared across the organization, team folders, granular roles, and SSO integration, at $14.99 per user per month. Enterprise plans receive custom storage sizes and a dedicated support engineer. All paid plans include 180 days of file version history and a 90-day recycle bin, compared with 30 days on the free plan.

## Maximum Upload Size

You can upload files up to **20 GB** in size through the desktop and mobile clients, and through the API. The web app has a separate, smaller limit: files uploaded through a browser are capped at **2 GB**. If a web upload fails near 2 GB, switch to the desktop client — this is expected behavior, not a bug. The 20 GB desktop limit was introduced in CloudBox 2.0 (September 2023); earlier versions were limited to 5 GB. Uploads that exceed the limit fail with the error "File too large".

## Transfer and Bandwidth Limits

Free plans include **200 GB per day** of combined upload and download traffic. Paid plans have no daily cap, subject to fair-use limits. Downloads of shared links by anonymous visitors count against the link owner's transfer limit. Desktop clients can throttle bandwidth per network in Settings > Network, which is useful on metered connections.

## Version History Quota Rules

Version history stores previous states of your files for 30 days on the free plan and 180 days on paid plans. Versions do not count against your storage quota, but the oldest versions are pruned automatically after the retention window. You can restore any previous version from the file's Version history panel in the web app.
