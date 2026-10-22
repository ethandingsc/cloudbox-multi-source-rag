---
title: Security: Two-Factor Authentication Policy — Practical notes
slug: synthetic-blog-063
source_type: blog
version: 2.1
date: 2024-09-02
topics: security, encryption, 2fa, passwords
synthetic: true
derived_from: docs:security:two-factor-authentication-policy
author: CloudBox Editorial
---

# Security: Two-Factor Authentication Policy — Practical notes

## What the guide says

A practical way to approach two-factor authentication policy is to start with the current Security guide. Two-factor authentication (2FA) is required for all organization accounts — this policy applies to every member of a team or business account and took effect with CloudBox 2.1 (May 2024). Organization members must enroll a TOTP authenticator app within 14 days of the policy applying; after that, un-enrolled accounts are locked out until enrollment. Organization administrators cannot disable this requirement. For personal accounts, 2FA remains optional but strongly recommended. When a forum answer or an old screenshot differs, check the maintained documentation before changing your setup. This note is a scenario-oriented summary of the same facts.
