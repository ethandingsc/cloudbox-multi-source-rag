---
title: Organizing Team Folders That Won't Collapse at Scale
slug: team-folder-structure
source_type: blog
version: 2.1
date: 2024-02-08
author: Tom Alvarez
topics: teams, folders, best-practices
---

# Organizing Team Folders That Won't Collapse at Scale

## The Case Against One Giant Folder

Every growing company starts with a single shared folder named something like "Company Files". It works for six people and collapses at sixty: nobody knows where contracts live, permissions become an all-or-nothing nightmare, and everyone's sync client churns through files they don't need. Restructuring later is painful, so get the shape right early.

## A Structure That Scales

Use CloudBox team folders as your top level, one per department — Sales, Engineering, Design, Operations. Inside each, two more levels at most: department > project or quarter. Example: `Engineering > [2024-Q3] Mobile App > Specs`. Resist a third level; depth hides files. Grant access at the team-folder level with member groups, not per file, so onboarding a new hire is one group assignment instead of forty link shares.

## Naming Conventions

Names sort lexicographically, so let the sort do the work. Prefix dates as YYYY-MM-DD, prefix drafts with a clear marker like `DRAFT-`, and ban special characters that break sync on some platforms (avoid `: * ? " < > |` in filenames). A consistent convention means search is predictable, which matters more than any folder hierarchy.

## When to Reorganize

Signs it's time: people ask "where do we keep X?" weekly, links to files break because someone moved a parent folder, or the top folder has more than thirty direct children. Reorganize off-peak, announce it, and move files in bulk using the desktop client rather than the web app. Never reorganize while freelancers hold active edit links — they'll lose their references.
