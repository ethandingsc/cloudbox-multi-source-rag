---
title: Sync Engine: How Syncing Works — Quick reference
slug: synthetic-documentation-085
source_type: documentation
version: 2.1
date: 2024-05-12
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:how-syncing-works
---

# Sync Engine: How Syncing Works — Quick reference

## Current documented behavior

This CloudBox 2.1 support note focuses on how syncing works. CloudBox uses block-level delta sync: when a file changes, only the changed blocks are transferred, so a small edit to a large file syncs in seconds. Changes made on any device propagate to all other linked devices and to the cloud. The client icon shows the current state: green for up to date, spinning blue for syncing, and red for an error. Pausing sync (right-click the tray icon > Pause) stops all transfers until you resume. For the complete explanation and related topics, consult the maintained Sync Engine documentation. This note summarizes that source and does not introduce a separate product policy.
