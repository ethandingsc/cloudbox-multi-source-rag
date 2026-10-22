---
title: Sync Engine: Sync Conflicts — Practical notes
slug: synthetic-blog-089
source_type: blog
version: 2.1
date: 2024-09-28
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:sync-conflicts
author: CloudBox Editorial
---

# Sync Engine: Sync Conflicts — Practical notes

## What the guide says

A practical way to approach sync conflicts is to start with the current Sync Engine guide. If the same file is edited in two places before either syncs, CloudBox keeps both versions: one keeps the original name and the other becomes "name (conflicted copy, YYYY-MM-DD, user)". Nothing is overwritten or lost. To resolve a conflict, compare the two files, decide which to keep, and delete the other. Conflicted copies behave like normal files and sync everywhere. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
