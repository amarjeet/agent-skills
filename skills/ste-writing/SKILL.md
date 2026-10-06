---
name: ste-writing
description: "Write or rewrite prose in ASD-STE100-style Simplified Technical English: short, literal sentences anyone can read without guessing. Accepts a target (where) and a mode (how). Triggers: ste, use ste, simplified technical english, asd-ste100, write in ste, rewrite in ste, plain technical english, make this unambiguous, ste review."
license: MIT
---

# STE Writing

## Overview

Apply ASD-STE100 rules to prose at a target and in a mode that the user names.

## Instructions

1. Read the invocation for **where** and **how**. Use the defaults if a value is missing.

   | Where (target) | Scope |
   |---|---|
   | `reply` (default) | Only the current answer |
   | `session` | Every answer until the user says `ste off` |
   | `<path or glob>` | Prose in those files: docs, comments, commit or PR text, UI strings |
   | pasted text | Only the text that the user gives |

   | How (mode) | Action |
   |---|---|
   | `write` (default for `reply`/`session`) | Write new content in STE |
   | `rewrite` (default for files and text) | Change existing prose to STE. Keep the meaning and the facts |
   | `review` | Do not edit. List each violation as `location · rule · fix` |

   Also obey free-text context, for example "for on-call runbooks" or "readers are non-native speakers". It sets the audience, the tone and the terms.

2. Apply the six rules to every sentence:
   1. Max 20 words per sentence. Max 25 words for a procedure step.
   2. One word, one meaning. Do not use one word for two ideas.
   3. Same term every time. Pick one name for each thing. Do not use synonyms ("data" stays "data", never "information").
   4. Active voice. Name who does the action.
   5. One idea per sentence. One instruction per step. Put the condition first: "If X, do Y."
   6. Simple, approved words. Use common words and simple verb tenses. Remove filler ("essentially", "basically", "considerably", "in order to").

3. Keep these unchanged: code, commands, identifiers, paths, URLs, quotations, product names. Technical nouns are allowed ("cache", "database"). Define each one at first use if the audience may not know it.

4. For files, edit only prose. Keep the structure, Markdown, and line format. Keep a terms list for the run. Use it to make the terms the same across all files.

5. After `rewrite` or `review`, add one stats line: `N sentences · max W words · T terms fixed`.

## Example

Input: `/ste-writing reply` "Explain what a cache is."

Output:
> A **cache** is a small, fast memory. It keeps a copy of **data** that you use frequently. When you need the **data**, the system reads the **cache** first. This is faster than reading the **database**. The **database** does less work.
