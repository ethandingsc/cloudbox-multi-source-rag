---
title: Team Accounts
slug: teams
source_type: documentation
version: 2.1
date: 2024-05-12
topics: teams, org, folders, roles
---

# Team Accounts

## Team Accounts and Roles

Business and Enterprise plans include team accounts with three roles. **Admins** manage membership, billing, and security settings. **Members** have full access to team folders according to their permissions. **Guests** are external people with limited access to specific folders only. Every role is tied to a named user account; shared accounts are not supported.

## Shared Team Folders

Team folders live in a separate namespace from personal files and are owned by the organization, not by individuals. Access is granted per folder to members or groups. When someone leaves the organization, their personal files are transferred to an admin-designated account and their team folder access is revoked immediately. Team folders cannot be converted back to personal folders.

## Organization Security Requirements

All organization accounts must enroll in two-factor authentication; this requirement took effect with CloudBox 2.1 and applies to every member, including guests. Organizations on Business and Enterprise plans can additionally enable SSO (SAML or OIDC), which centralizes sign-in but does not replace the 2FA requirement. Admins can audit devices and sessions from the admin console and remotely sign out a lost laptop.
