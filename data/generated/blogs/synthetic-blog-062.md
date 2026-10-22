---
title: Security: Encryption at Rest and in Transit — What to check
slug: synthetic-blog-062
source_type: blog
version: 2.1
date: 2024-09-01
topics: security, encryption, 2fa, passwords
synthetic: true
derived_from: docs:security:encryption-at-rest-and-in-transit
author: CloudBox Editorial
---

# Security: Encryption at Rest and in Transit — What to check

## What the guide says

A practical way to approach encryption at rest and in transit is to start with the current Security guide. Encryption keys are managed by CloudBox's key management service, with automatic rotation. Note that CloudBox does not currently offer a client-side (zero-knowledge) encryption option; files are encrypted with keys held by CloudBox, which is what allows server-side features such as previews and virus scanning. CloudBox encrypts all files at rest with AES-256 and all traffic in transit with TLS 1.3. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
