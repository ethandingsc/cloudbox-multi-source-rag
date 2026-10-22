---
title: API Reference: Uploading Files via the API — What to check
slug: synthetic-blog-008
source_type: blog
version: 2.1
date: 2024-07-09
topics: api, developers, rate-limits, upload
synthetic: true
derived_from: docs:api:uploading-files-via-the-api
author: CloudBox Editorial
---

# API Reference: Uploading Files via the API — What to check

## What the guide says

A practical way to approach uploading files via the api is to start with the current API Reference guide. Start an upload session, PUT the chunks, then finalize. Failed chunks can be retried individually. Files uploaded via the API appear in the designated folder immediately and inherit its sharing settings. The API supports resumable chunked uploads of files up to 20 GB, the same ceiling as the desktop clients — the 2 GB web-app cap does not apply to the API. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
