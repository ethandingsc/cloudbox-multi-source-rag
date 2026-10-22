---
title: Sync Engine: How Syncing Works — Practical notes
slug: synthetic-blog-085
source_type: blog
version: 2.1
date: 2024-09-24
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:how-syncing-works
author: CloudBox Editorial
---

# Sync Engine: How Syncing Works — Practical notes

## What the guide says

A practical way to approach how syncing works is to start with the current Sync Engine guide. CloudBox uses block-level delta sync: when a file changes, only the changed blocks are transferred, so a small edit to a large file syncs in seconds. Changes made on any device propagate to all other linked devices and to the cloud. The client icon shows the current state: green for up to date, spinning blue for syncing, and red for an error. Pausing sync (right-click the tray icon > Pause) stops all transfers until you resume. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
