---
title: API Reference: Rate Limits — Quick reference
slug: synthetic-documentation-004
source_type: documentation
version: 2.1
date: 2024-05-12
topics: api, developers, rate-limits, upload
synthetic: true
derived_from: docs:api:rate-limits
---

# API Reference: Rate Limits — Quick reference

## Current documented behavior

This CloudBox 2.1 support note focuses on rate limits. API requests are limited to 1000 requests per hour per token. When the limit is hit, the API returns HTTP 429 with a Retry-After header; clients should implement exponential backoff. Burst allowances are not available. Read-only endpoints (listing, metadata) count the same as writes. For the complete explanation and related topics, consult the maintained API Reference documentation. This note summarizes that source and does not introduce a separate product policy.
