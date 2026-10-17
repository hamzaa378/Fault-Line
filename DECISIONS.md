# Technical decisions (notes to personalize before submission)

The recruitment brief suggests answering these questions in your **own words**. These are implementation facts and prompts, not a personal account written on your behalf.

## What was the hardest technical part?

Two independent ordering problems: the event's occurrence clock versus its arrival clock, and competing writes to the same incident. The system preserves both timestamps and presents alternate chronological views. Incident edits use an atomic `UPDATE ... WHERE version = expected_version` to prevent silent last-write-wins overwrites. Notes are append-only, so collaborators can add evidence without editing the incident record.

## One design choice and why

Use a relational, transactional PostgreSQL model for incidents, memberships, audit records, and event identities, instead of keeping all state in browser memory or using best-effort deduplication. Unique constraints enforce `(project_id, source, external_id)` at the database boundary. This makes retries predictable even if the UI refreshes or two ingesters race.

## What is the main limitation?

The deployment-suspect score is an interpretable rule-based hypothesis generator, not a root-cause detector. A nearby release on the same service is a useful investigation lead but does not establish causality. Webhooks currently store event evidence, not a full transformation into deployment/change domain records. Also see `docs/RISK_AND_LIMITATIONS.md`.

## What would you improve with another week?

Prioritize a reproducible PostgreSQL parallel-write benchmark, a versioned migration strategy, and secure session handling before adding more UI features. Then enrich integration with repository identity validation and more precise commit/deployment attribution. Explain which of these you personally implemented and verified, with dates and evidence.
