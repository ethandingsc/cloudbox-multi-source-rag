---
title: Selective Sync
slug: selective-sync
source_type: documentation
version: 2.1
date: 2024-05-12
topics: selective-sync, storage, disk-space
---

# Selective Sync

## What Is Selective Sync

Selective sync, introduced in CloudBox 2.0, lets each device choose which folders are stored locally. Folders you exclude stay in the cloud and remain accessible through the web app and mobile clients, but they do not use disk space on that device. Selective sync settings are per device: excluding a folder on your laptop does not affect your desktop.

## Setting Up Selective Sync

Open the desktop client's Preferences, go to the Sync tab, and choose Selective Sync. Uncheck the folders you want to keep cloud-only, then confirm. The local copies are removed from disk and the folder appears with a cloud-only badge. To bring a folder back, simply check it again — its contents re-download automatically. Excluded folders still count toward your storage quota, since they remain in the cloud.

## Limitations and Best Practices

Selective sync is available on Windows, macOS, and Linux desktop clients but not on mobile. Use it for large archive folders and completed projects rather than folders you actively edit on that device. Remember that excluded folders are protected only by the cloud: if someone deletes them from the web app, the cloud copy is gone. CloudBox recommends keeping at least one device with the folder synced locally if it contains irreplaceable data.
