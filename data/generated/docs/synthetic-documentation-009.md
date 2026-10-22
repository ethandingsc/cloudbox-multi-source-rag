---
title: API Reference: Uploading Files via the API — Common questions
slug: synthetic-documentation-009
source_type: documentation
version: 2.1
date: 2024-05-12
topics: api, developers, rate-limits, upload
synthetic: true
derived_from: docs:api:uploading-files-via-the-api
---

# API Reference: Uploading Files via the API — Common questions

## Current documented behavior

This CloudBox 2.1 support note focuses on uploading files via the api. Failed chunks can be retried individually. Files uploaded via the API appear in the designated folder immediately and inherit its sharing settings. The API supports resumable chunked uploads of files up to 20 GB, the same ceiling as the desktop clients — the 2 GB web-app cap does not apply to the API. Start an upload session, PUT the chunks, then finalize. For the complete explanation and related topics, consult the maintained API Reference documentation. This note summarizes that source and does not introduce a separate product policy.
