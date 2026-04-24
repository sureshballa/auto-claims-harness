# Mock data for the auto-claims harness

This directory holds the seed data used by tests, evals, and the
dev-time agent. The data is **synthetic** — names, IDs, VINs, and
emails are fabricated. The `.test` TLD on emails is reserved by IANA
and will never resolve to a real address.

## Files

- `policies.json` — 50 policies. Generated.
- `claims.json` — 20 claims. Generated. Includes adversarial cases.

## Adversarial cases

These three claims exist to exercise the harness's failure paths:

- `CLM-00018` — incident_date precedes the policy's effective date
- `CLM-00019` — references `POL-99999`, which doesn't exist
- `CLM-00020` — incident_type=THEFT against a policy lacking COMPREHENSIVE

The harness must handle each gracefully. They are features, not bugs.

## Regenerating

```bash
uv run python scripts/generate_mock_data.py
```

The generator is seeded (`random.seed(42)`); output is reproducible.
Commit the regenerated files; the script's RNG seed is the source of
truth for what's in the JSON.

## What this data is NOT

Production-realistic. The names, distributions, and coverage configurations
are simplified to exercise the harness, not to represent real-world claim
patterns. For evaluation against realistic distributions, see `evals/`.
