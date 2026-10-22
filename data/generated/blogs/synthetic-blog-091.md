---
title: Sync Engine: Troubleshooting Sync Issues — Practical notes
slug: synthetic-blog-091
source_type: blog
version: 2.1
date: 2024-09-30
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:troubleshooting-sync-issues
author: CloudBox Editorial
---

# Sync Engine: Troubleshooting Sync Issues — Practical notes

## What the guide says

A practical way to approach troubleshooting sync issues is to start with the current Sync Engine guide. If the client is stuck on "Syncing…" for more than a few minutes: pause and resume sync; check your proxy or firewall settings (CloudBox uses port 443); clear the local cache under Settings > Advanced; then restart the client. If the problem persists, collect the logs from the client's logs folder and open a support ticket. The most common causes are corporate proxies, antivirus scanning of the sync folder, and file locks from other applications. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
