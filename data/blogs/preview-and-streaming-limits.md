---
title: Preview and Streaming Limits, Explained
slug: preview-and-streaming-limits
source_type: blog
version: 2.0
date: 2023-08-03
author: Ravi Patel
topics: preview, streaming, video, limits
---

# Preview and Streaming Limits, Explained

## Why Previews Are Capped

When you preview a video in the browser, CloudBox transcodes it on the fly. Transcoding is expensive, and unbounded previews would mean our servers happily burning money on 50 GB raw files. So previews have a hard cap, and everything above it shows a download button instead. It's not a file problem — it's an economics problem.

## Current Preview Limits

In CloudBox 2.0, files up to 500 MB can be previewed or streamed in the browser: documents, PDFs, images, and video/audio. Files larger than 500 MB must be downloaded before viewing. Previews are generated on demand and never stored, so re-watching a clip means re-transcoding — another reason the cap exists.

## Streaming vs Downloading

If you need to watch a 3 GB video, download it. The desktop client plays files locally with no preview cap, so the smoothest workflow is: let the file sync, play it from the local folder. On the web, the download button on a large file is expected behavior, not a bug — and remember the separate question of upload limits, which follow different rules entirely.
