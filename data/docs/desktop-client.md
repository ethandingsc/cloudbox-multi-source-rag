---
title: Desktop Client
slug: desktop-client
source_type: documentation
version: 2.1
date: 2024-05-12
topics: desktop, install, bandwidth, proxy
---

# Desktop Client

## Installing the Desktop Client

Download the desktop client from the CloudBox download page. Supported platforms: Windows 10 or newer, macOS 11 or newer, and Linux (Ubuntu 20.04+ / Fedora 36+, via .deb package or AppImage — available since CloudBox 2.0). After installation, sign in and choose which folders to sync; the default is your entire CloudBox folder with selective sync available for fine control.

## Bandwidth and Network Settings

The client lets you throttle upload and download bandwidth per network in Settings > Network, so a metered hotspot is never drained by background syncs. On paid plans, "Smart Sync" learns your working hours and schedules large transfers for off-peak times. LAN sync accelerates transfers between devices on the same local network without going through the cloud.

## Proxy and Firewall Support

The desktop client honors HTTP and SOCKS5 proxies configured in Settings > Network, and it respects the system proxy by default. All traffic goes to CloudBox over port 443; firewalls that allow standard HTTPS need no extra rules. Corporate environments with TLS inspection may cause "Syncing…" to stall — add an exception for the CloudBox endpoints or contact support for the enterprise network guide.
