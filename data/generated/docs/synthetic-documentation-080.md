---
title: Storage Limits: Maximum Upload Size — Expected behavior
slug: synthetic-documentation-080
source_type: documentation
version: 2.1
date: 2024-05-12
topics: storage, quota, plans, upload
synthetic: true
derived_from: docs:storage-limits:maximum-upload-size
---

# Storage Limits: Maximum Upload Size — Expected behavior

## Current documented behavior

This CloudBox 2.1 support note focuses on maximum upload size. The web app has a separate, smaller limit: files uploaded through a browser are capped at 2 GB. If a web upload fails near 2 GB, switch to the desktop client — this is expected behavior, not a bug. The 20 GB desktop limit was introduced in CloudBox 2.0 (September 2023); earlier versions were limited to 5 GB. Uploads that exceed the limit fail with the error "File too large". For the complete explanation and related topics, consult the maintained Storage Limits documentation. This note summarizes that source and does not introduce a separate product policy.
