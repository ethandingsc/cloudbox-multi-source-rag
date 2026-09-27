---
title: How to Set Up Selective Sync (and Reclaim Your SSD)
slug: selective-sync-tutorial
source_type: blog
version: 2.1
date: 2024-06-03
author: Maya Chen
topics: selective-sync, disk-space, desktop
---

# How to Set Up Selective Sync (and Reclaim Your SSD)

## Why Selective Sync Matters

If your team laptop has a 256 GB SSD, syncing the entire company CloudBox is simply not an option. Selective sync — available since CloudBox 2.0 — solves this: each device decides which folders live on its disk, while everything else stays safely in the cloud and remains reachable through the web app. My rule of thumb: keep the folders you edit this week local, and let the archive folders live cloud-only.

## Step-by-Step Setup

Open the desktop client's Preferences, go to the Sync tab, and pick Selective Sync. You will see your full folder tree with checkboxes. Uncheck the folders you want to keep cloud-only and confirm — the local copies are removed from disk and the folder shows a cloud-only badge. Want a folder back? Check it again and it re-downloads. Remember two things: these settings are per device, and excluded folders still count toward your storage quota because the cloud copy remains.

## Tips for Small SSDs

Start with the obvious space hogs: raw video, old project archives, and anything you only open once a quarter. Keep current projects local so edits stay fast. Check Settings > Advanced > Clear local cache every few months — the sync cache can quietly grow. And remember the preview cap: files over 500 MB will not stream in the browser, so don't exclude a video folder and expect to watch from the web app — plan to download those.
