---
title: Sync Engine: Troubleshooting Sync Issues — Expected behavior
slug: synthetic-documentation-092
source_type: documentation
version: 2.1
date: 2024-05-12
topics: sync, linux, desktop, conflicts
synthetic: true
derived_from: docs:sync:troubleshooting-sync-issues
---

# Sync Engine: Troubleshooting Sync Issues — Expected behavior

## Current documented behavior

This CloudBox 2.1 support note focuses on troubleshooting sync issues. If the problem persists, collect the logs from the client's logs folder and open a support ticket. The most common causes are corporate proxies, antivirus scanning of the sync folder, and file locks from other applications. If the client is stuck on "Syncing…" for more than a few minutes: pause and resume sync; check your proxy or firewall settings (CloudBox uses port 443); clear the local cache under Settings > Advanced; then restart the client. For the complete explanation and related topics, consult the maintained Sync Engine documentation. This note summarizes that source and does not introduce a separate product policy.
