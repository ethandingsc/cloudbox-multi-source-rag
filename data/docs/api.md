---
title: API Reference
slug: api
source_type: documentation
version: 2.1
date: 2024-05-12
topics: api, developers, rate-limits, upload
---

# API Reference

## API Overview

The CloudBox REST API provides programmatic access to files, folders, share links, and account metadata. Authentication uses OAuth2 bearer tokens created in the developer console. Responses are JSON, and all endpoints are versioned under `/v1`. The API is available on all plans; Business and Enterprise plans receive higher rate limits on request.

## Rate Limits

API requests are limited to **1000 requests per hour per token**. When the limit is hit, the API returns HTTP 429 with a `Retry-After` header; clients should implement exponential backoff. Burst allowances are not available. Read-only endpoints (listing, metadata) count the same as writes.

## Uploading Files via the API

The API supports resumable chunked uploads of files up to **20 GB**, the same ceiling as the desktop clients — the 2 GB web-app cap does not apply to the API. Start an upload session, PUT the chunks, then finalize. Failed chunks can be retried individually. Files uploaded via the API appear in the designated folder immediately and inherit its sharing settings.
