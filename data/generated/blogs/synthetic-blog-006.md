---
title: API Reference: Rate Limits — A closer look
slug: synthetic-blog-006
source_type: blog
version: 2.1
date: 2024-07-07
topics: api, developers, rate-limits, upload
synthetic: true
derived_from: docs:api:rate-limits
author: CloudBox Editorial
---

# API Reference: Rate Limits — A closer look

## What the guide says

A practical way to approach rate limits is to start with the current API Reference guide. Burst allowances are not available. Read-only endpoints (listing, metadata) count the same as writes. API requests are limited to 1000 requests per hour per token. When the limit is hit, the API returns HTTP 429 with a Retry-After header; clients should implement exponential backoff. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
