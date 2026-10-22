---
title: Desktop Client: Proxy and Firewall Support — Common questions
slug: synthetic-documentation-027
source_type: documentation
version: 2.1
date: 2024-05-12
topics: desktop, install, bandwidth, proxy
synthetic: true
derived_from: docs:desktop-client:proxy-and-firewall-support
---

# Desktop Client: Proxy and Firewall Support — Common questions

## Current documented behavior

This CloudBox 2.1 support note focuses on proxy and firewall support. Corporate environments with TLS inspection may cause "Syncing…" to stall — add an exception for the CloudBox endpoints or contact support for the enterprise network guide. The desktop client honors HTTP and SOCKS5 proxies configured in Settings > Network, and it respects the system proxy by default. All traffic goes to CloudBox over port 443; firewalls that allow standard HTTPS need no extra rules. For the complete explanation and related topics, consult the maintained Desktop Client documentation. This note summarizes that source and does not introduce a separate product policy.
