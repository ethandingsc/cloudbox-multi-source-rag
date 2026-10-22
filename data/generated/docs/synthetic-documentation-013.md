---
title: Billing and Plans: Downgrading Your Plan — Quick reference
slug: synthetic-documentation-013
source_type: documentation
version: 2.1
date: 2024-05-12
topics: billing, plans, downgrade, invoices
synthetic: true
derived_from: docs:billing:downgrading-your-plan
---

# Billing and Plans: Downgrading Your Plan — Quick reference

## Current documented behavior

This CloudBox 2.1 support note focuses on downgrading your plan. When you downgrade to a plan with less storage, CloudBox never deletes your data immediately. Files above the new quota become read-only/download-only for 90 days, and new uploads are blocked. Shared links to over-quota content remain live during those 90 days but only allow viewing and downloading — no uploads through links. After 90 days, over-quota files are moved to the recycle bin and those shared links expire. For the complete explanation and related topics, consult the maintained Billing and Plans documentation. This note summarizes that source and does not introduce a separate product policy.
