---
title: The Linux Client Is Finally Here
slug: linux-client-arrives
source_type: blog
version: 2.0
date: 2023-09-12
author: Maya Chen
topics: linux, desktop, release
---

# The Linux Client Is Finally Here

## The Long Wait Is Over

After two years of feature-request votes, CloudBox 2.0 ships with an official Linux desktop client. Ubuntu and Fedora users get the same experience as Windows and macOS: background sync, tray integration, selective sync, and bandwidth throttling. No more browser-only workarounds for the penguin crowd.

## Supported Distributions

The client officially supports Ubuntu 20.04 LTS and newer, and Fedora 36 and newer. Packages come as a `.deb` for Ubuntu/Debian systems and an AppImage that runs on most other distributions. Arch users will find community packaging within days, we're sure. Anything else is best-effort: it may run, but support tickets on unsupported distros are lower priority.

## What About Headless Servers?

A full desktop client needs a desktop, so for servers we're shipping the CloudBox CLI: a small command-line tool that handles uploads and downloads (up to the standard 20 GB file limit) with resumable transfers. It does not do background sync — if you want automated sync on a NAS or server, you'll be scripting the CLI with cron or systemd timers. We know a daemon is the real ask; consider this the first step.
