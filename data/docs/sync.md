---
title: Sync Engine
slug: sync
source_type: documentation
version: 2.1
date: 2024-05-12
topics: sync, linux, desktop, conflicts
---

# Sync Engine

## How Syncing Works

CloudBox uses block-level delta sync: when a file changes, only the changed blocks are transferred, so a small edit to a large file syncs in seconds. Changes made on any device propagate to all other linked devices and to the cloud. The client icon shows the current state: green for up to date, spinning blue for syncing, and red for an error. Pausing sync (right-click the tray icon > Pause) stops all transfers until you resume.

## Linux Desktop Client

CloudBox has shipped an official **Linux desktop client since version 2.0** (September 2023). Supported distributions are Ubuntu 20.04 LTS or newer and Fedora 36 or newer; both `.deb` packages and AppImages are provided. The Linux client has feature parity with the Windows and macOS clients, including selective sync and bandwidth throttling. Older forum posts stating that Linux is unsupported refer to versions before 2.0.

## Sync Conflicts

If the same file is edited in two places before either syncs, CloudBox keeps both versions: one keeps the original name and the other becomes "name (conflicted copy, YYYY-MM-DD, user)". Nothing is overwritten or lost. To resolve a conflict, compare the two files, decide which to keep, and delete the other. Conflicted copies behave like normal files and sync everywhere.

## Troubleshooting Sync Issues

If the client is stuck on "Syncing…" for more than a few minutes: pause and resume sync; check your proxy or firewall settings (CloudBox uses port 443); clear the local cache under Settings > Advanced; then restart the client. If the problem persists, collect the logs from the client's logs folder and open a support ticket. The most common causes are corporate proxies, antivirus scanning of the sync folder, and file locks from other applications.

## Local Cache and Disk Usage

The client keeps a local cache of recently changed blocks to make syncs faster; this cache can grow large on busy folders. You can clear it at any time under Settings > Advanced without affecting your files. The cache never counts against your CloudBox storage quota — it is a local, per-device artifact only.
