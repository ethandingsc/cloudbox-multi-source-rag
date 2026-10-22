---
title: Sync Engine: Sync Conflicts — Quick reference
slug: synthetic-documentation-089
source_type: documentation
version: 2.1
date: 2024-05-12
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:sync-conflicts
---

# Sync Engine: Sync Conflicts — Quick reference

## Current documented behavior

This CloudBox 2.1 support note focuses on sync conflicts. If the same file is edited in two places before either syncs, CloudBox keeps both versions: one keeps the original name and the other becomes "name (conflicted copy, YYYY-MM-DD, user)". Nothing is overwritten or lost. To resolve a conflict, compare the two files, decide which to keep, and delete the other. Conflicted copies behave like normal files and sync everywhere. For the complete explanation and related topics, consult the maintained Sync Engine documentation. This note summarizes that source and does not introduce a separate product policy.
