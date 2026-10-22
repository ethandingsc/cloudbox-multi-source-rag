---
title: Desktop Client: Proxy and Firewall Support — What to check
slug: synthetic-blog-026
source_type: blog
version: 2.1
date: 2024-07-27
topics: desktop, install, bandwidth, proxy
synthetic: true
derived_from: docs:desktop-client:proxy-and-firewall-support
author: CloudBox Editorial
---

# Desktop Client: Proxy and Firewall Support — What to check

## What the guide says

A practical way to approach proxy and firewall support is to start with the current Desktop Client guide. All traffic goes to CloudBox over port 443; firewalls that allow standard HTTPS need no extra rules. Corporate environments with TLS inspection may cause "Syncing…" to stall — add an exception for the CloudBox endpoints or contact support for the enterprise network guide. The desktop client honors HTTP and SOCKS5 proxies configured in Settings > Network, and it respects the system proxy by default. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
