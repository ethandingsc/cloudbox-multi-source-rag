---
title: Sharing Files and Folders
slug: file-sharing
source_type: documentation
version: 2.1
date: 2024-05-12
topics: sharing, links, permissions, external-users, preview, upload
---

# Sharing Files and Folders

## Sharing Files and Folders

To share a file or folder, right-click it in any CloudBox client and choose Share, or use the Share button in the web app. Pick a permission level — **View** (read-only), **Edit** (add and modify files), or **Comment** (read and leave comments) — then copy the generated link. By default the link works for anyone who has it; switch to "Specific people" to restrict access to named individuals or groups.

## Link Permissions and Expiry

Share links can carry an optional **expiration date** and an optional **password**. Expired links stop working immediately, and you can revoke any link at any time from the Shared links panel. Changing a file's permissions applies to every link that points to it. Links to folders inherit the folder's permissions.

## External Users

People outside your organization do not need a CloudBox account to access a share link. Anonymous visitors can view and download; to edit or comment they must enter a name (and optionally sign in). External users with Edit permission on a folder can upload files to it — their uploads count against the folder owner's quota. You can convert an external user into a guest account from the Sharing settings of the folder.

## Preview and Streaming Limits

The web app can preview and stream files up to **500 MB**, including documents, PDFs, images, and video/audio. Files larger than 500 MB must be downloaded before viewing. Previews are generated on demand and are not stored. The desktop and mobile clients play video locally, so the 500 MB preview cap does not apply to them.

## Uploading Through the Web App

Uploads made through a browser are capped at **2 GB per file**. For larger files, use the desktop or mobile client, which support uploads up to 20 GB. A web upload that exceeds 2 GB fails partway through with no data saved; you can retry it from the desktop client without corrupting anything. The API also supports uploads up to 20 GB.
