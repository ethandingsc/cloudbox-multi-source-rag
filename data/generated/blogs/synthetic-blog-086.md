---
title: Sync Engine: How Syncing Works — What to check
slug: synthetic-blog-086
source_type: blog
version: 2.1
date: 2024-09-25
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:how-syncing-works
author: CloudBox Editorial
---

# Sync Engine: How Syncing Works — What to check

## What the guide says

A practical way to approach how syncing works is to start with the current Sync Engine guide. Changes made on any device propagate to all other linked devices and to the cloud. The client icon shows the current state: green for up to date, spinning blue for syncing, and red for an error. Pausing sync (right-click the tray icon > Pause) stops all transfers until you resume. CloudBox uses block-level delta sync: when a file changes, only the changed blocks are transferred, so a small edit to a large file syncs in seconds. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
