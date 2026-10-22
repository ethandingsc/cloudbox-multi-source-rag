---
title: Security: Encryption at Rest and in Transit — Quick reference
slug: synthetic-documentation-061
source_type: documentation
version: 2.1
date: 2024-05-12
topics: security, encryption, 2fa, passwords
synthetic: true
derived_from: docs:security:encryption-at-rest-and-in-transit
---

# Security: Encryption at Rest and in Transit — Quick reference

## Current documented behavior

This CloudBox 2.1 support note focuses on encryption at rest and in transit. CloudBox encrypts all files at rest with AES-256 and all traffic in transit with TLS 1.3. Encryption keys are managed by CloudBox's key management service, with automatic rotation. Note that CloudBox does not currently offer a client-side (zero-knowledge) encryption option; files are encrypted with keys held by CloudBox, which is what allows server-side features such as previews and virus scanning. For the complete explanation and related topics, consult the maintained Security documentation. This note summarizes that source and does not introduce a separate product policy.
