---
title: Sync Engine: Local Cache and Disk Usage — Quick reference
slug: synthetic-documentation-093
source_type: documentation
version: 2.1
date: 2024-05-12
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:local-cache-and-disk-usage
---

# Sync Engine: Local Cache and Disk Usage — Quick reference

## Current documented behavior

This CloudBox 2.1 support note focuses on local cache and disk usage. The client keeps a local cache of recently changed blocks to make syncs faster; this cache can grow large on busy folders. You can clear it at any time under Settings > Advanced without affecting your files. The cache never counts against your CloudBox storage quota — it is a local, per-device artifact only. For the complete explanation and related topics, consult the maintained Sync Engine documentation. This note summarizes that source and does not introduce a separate product policy.
