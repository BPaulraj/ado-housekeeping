---
description: "Prepare 1:1 coaching notes for a tester from the latest tqa digest"
agent: "agent"
argument-hint: "Tester name, or 'all'"
---

Prepare private 1:1 coaching notes for the test manager. Tester(s): ${input:tester:all}

## Input
Use the attached digest, or the newest sprint digest `reports/*_digest.json` (not a `trends_` one). If a trends digest (`reports/*trends_*_digest.json`) exists, also use the tester's series and `signals`, and say whether a pattern is new or persistent, e.g. "third sprint over capacity". Use `contribution.people` (effort, output, quality, flow, collaboration, observations), plus `testers`, `hygiene.by_person` and `stories` for context.

## Principles
- The purpose is **balancing and coaching**, not rating. Never compare testers with each other or rank them.
- Only use facts from the digest. An observation is a **question to explore**, not a conclusion. Low logged hours can mean blocked, working on things outside ADO, or not logging.
- Read the numbers in context. Someone on performance work will have few executions; an automation specialist will have mostly automation hours.
- Where `bug_reasons_maintained` is false or `has_code_data` is false, don't comment on bug rejection or code.

## Output per tester (Markdown, `### Name`, at most ~200 words each)
1. **Sprint in one line:** what their sprint mostly consisted of (effort mix, main stories).
2. **Recognise (1–3):** specific strengths with numbers, e.g. "reviewed 24 test cases written by others".
3. **Explore (1–3):** each observation turned into an open question, e.g. "Hours were 26% of capacity – was anything blocking you, or work we don't see in ADO?"
4. **Growth suggestion (1):** one development focus that fits their pattern, e.g. rotate into test design, pair on automation, own the evidence reviews.
5. **Workload for next sprint:** keep / reduce / increase, with the reason.

Don't save the notes to a file unless the user asks. They're personal.
