---
title: Security
slug: security
source_type: documentation
version: 2.1
date: 2024-05-12
topics: security, encryption, 2fa, passwords
---

# Security

## Encryption at Rest and in Transit

CloudBox encrypts all files **at rest with AES-256** and all traffic **in transit with TLS 1.3**. Encryption keys are managed by CloudBox's key management service, with automatic rotation. Note that CloudBox does not currently offer a client-side (zero-knowledge) encryption option; files are encrypted with keys held by CloudBox, which is what allows server-side features such as previews and virus scanning.

## Two-Factor Authentication Policy

Two-factor authentication (2FA) is **required for all organization accounts** — this policy applies to every member of a team or business account and took effect with CloudBox 2.1 (May 2024). Organization members must enroll a TOTP authenticator app within 14 days of the policy applying; after that, un-enrolled accounts are locked out until enrollment. Organization administrators cannot disable this requirement. For personal accounts, 2FA remains optional but strongly recommended.

## Password and Account Rules

Account passwords must be at least 12 characters and cannot appear in known breach lists. Password resets are handled by verified email. The Security panel of the web app lists all active sessions and lets you sign out individual devices. Repeated failed login attempts trigger a temporary lockout and an email notification.

## Recovery Codes and Account Lockout

When you enroll in 2FA you receive 10 one-time recovery codes; store them somewhere safe, because they are the only way back in if you lose your authenticator. If you lose both your authenticator and your codes, you must complete an identity verification with support, which takes up to 48 hours. Organization accounts additionally allow an administrator to reset a member's 2FA from the admin console.
