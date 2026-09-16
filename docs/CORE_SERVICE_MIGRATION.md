# Private Core service migration — preparatory implementation

## Status

This branch **does not switch the active v1.21.0 coordinator to a remote service**.
The existing bundled core, QR wallet, generated-number records, actual reviews,
entity IDs, settings and stable release remain in place until the migration
preconditions below are met. This is not a completed core extraction or a new
production release.

## Added implementation

- `service_contract.py`: strict, calculation-free catalog and generation DTOs;
  context/version/number checks; drops upstream private details and summaries.
- `lab_client.py`: HTTPS-only production API transport, scoped bearer auth,
  disabled redirects, bounded messages/timeouts, safe status errors and stable
  idempotency keys. Explicit loopback HTTP is for local tests only.
- `remote_generation.py`: Store-compatible durable request reservation,
  same-key retry after restart, committed-result publication, independent from
  the wallet. Personal-request recovery before acknowledgement is a deliberate
  fail-closed state pending a service recovery endpoint.
- `tests/test_lab_service_client.py`: 19 targeted protocol/transport/persistence
  cases. These are not real user-HA or production-service tests.

## Required server contract (not deployed by this branch)

`GET /v1/formulas`, `POST /v1/generations`,
`GET /v1/generations/{id}`, `POST /v1/generations/{id}/cancel`.
Requests include contract version 1, an idempotency request key, target round,
selected formula IDs and public options. Optional personal input requires
explicit consent. No GitHub repository token is accepted as a deployment plan.
The server must authenticate the account/device, enforce ownership and resource
limits, reject changed request bodies under an existing key, pin the core/data,
commit the result durably, then return `completed` with server generation time.
Catalogs and results use the independent core's public projection, never raw
internal `generate_json()` output.

## Before the actual HA cutover

1. Finish the 16-module source import and independent private Core package in
   `1bobby-git/Lotto-Lab-Core`. The original source is pinned to
   `2e68bfbeaf8e19331b2b60a4a3f26f5c8bbba238`.
2. Provide an actual reachable service endpoint and scoped device authorization.
   Confirm server-execution vs customer-runtime distribution and HA usage policy.
3. Connect the client through configuration, reauthentication, per-entry catalog,
   coordinator generation/AI/consensus, and the real review snapshot lifecycle.
   The current module-global metadata must not become shared account state.
4. Preserve and migrate stored data. Wallet startup and offline result checking
   must not fail because the generation API is unavailable.
5. Validate that exact flow in the supported HA environment; only then remove
   bundled core code, compatibility imports and public Core release build steps.
6. Publish a stable release only after the deployed endpoint, QR workflow,
   current-round generation and pre-draw review all work together.

The temporary public `codex/source-snapshot` branch only archives an already
public pinned commit and downloads declared public dependencies. It must not be
merged. No new private core code or private credentials are put into public CI.
