---
title: How CloudBox Encryption Actually Works
slug: encryption-deep-dive
source_type: blog
version: 2.1
date: 2024-01-30
author: Ravi Patel
topics: encryption, security, at-rest
---

# How CloudBox Encryption Actually Works

## AES-256 at Rest

Every file you store is encrypted at rest with AES-256 in Galois/Counter Mode. When you upload a file, it is split into blocks, each block is encrypted before it touches a storage server, and decryption happens on the fly when you download. Server-side features like previews and virus scanning work because CloudBox holds the keys — more on that trade-off below.

## TLS 1.3 Everywhere

Traffic between your clients and CloudBox runs over TLS 1.3 exclusively; older protocol versions were disabled in 2023. Clients pin certificates to make man-in-the-middle interception visible, which is also why TLS-inspecting corporate firewalls occasionally cause sync stalls — the client can tell something is standing in the middle.

## Key Management

Encryption keys live in CloudBox's key management service, are rotated automatically, and are never written to logs or backups. Access is audited. The honest trade-off: because CloudBox holds the keys, a compromised CloudBox account or a legal request can expose your files. That's the price of previews, search, and server-side virus scanning.

## What Encryption Does Not Protect

Encryption protects data in CloudBox's custody. It does not protect: anyone you've shared a link with (they have access by design), screenshots or exports you make on your own device, a compromised laptop, or files stored outside CloudBox. If you need privacy from CloudBox itself, encrypt files client-side before uploading — there's no zero-knowledge option today.
