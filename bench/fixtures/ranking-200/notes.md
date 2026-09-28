<!-- delta:synth.note.plural01 -->
Situation: running database migrations on the billing service
Note: Run migrations against a snapshot first; the billing schema has triggers that the ORM does not model.
Why: A failed migration left invoices half-written last quarter.
aliases: schema, orm, invoices

<!-- delta:synth.note.plural02 -->
Situation: editing retry policies for the job queue
Note: Change the policy file, not the worker defaults; workers read the policy at start and ignore later env changes.
Why: Two outages came from edits that never took effect.
aliases: backoff, worker, queue

<!-- delta:synth.note.plural03 -->
Situation: adding dependencies to a leaf package
Note: Declare the dependency in the leaf package manifest; the root lockfile is regenerated in CI and hand edits are lost.
aliases: lockfile, manifest

<!-- delta:synth.note.plural04 -->
Situation: planning a rollback of the auth service
Note: Roll back auth by redeploying the previous image; database changes in auth are forward-only.
Why: A schema downgrade once locked every user out.
aliases: redeploy, image

<!-- delta:synth.note.substr01 -->
Situation: choosing the art direction for the marketing site
Note: Use the brand kit colors; the design team rejects ad hoc palettes.
aliases: design, brand, palette

<!-- delta:synth.note.substr02 -->
Situation: reading service logs during an incident
Note: Query the log index by trace ID first; grepping raw log files misses rotated segments.
Why: Rotated segments hold most of an incident's first minutes.
aliases: trace, incident

<!-- delta:synth.note.rare01 -->
Situation: agent changed the ledger rounding mode in billing
Note: Ledger rounding must stay banker's rounding; finance reconciles against it nightly.
Why: A rounding change produced a one-cent drift across 40,000 invoices.
aliases: rounding, finance, reconcile

<!-- delta:synth.note.rare02 -->
Situation: the agent ran the full test suite for a docs-only change
Note: For changes under docs/, run only the docs link check; the full suite takes forty minutes and proves nothing here.
aliases: docs, link check

<!-- delta:synth.note.sup01old -->
Situation: rotating the payments API key
Note: Rotate the key in the vault UI, then restart the gateway by hand.
aliases: vault, gateway, secret
Superseded-by: synth.note.sup01new

<!-- delta:synth.note.sup01new -->
Situation: rotating the payments API key
Note: Rotate the key with the rotate-secret job; it restarts the gateway and records the rotation.
Why: Manual restarts were missed twice and left the old key live.
aliases: vault, gateway, secret

<!-- delta:synth.note.mono01 -->
Situation: changing a public function signature in a shared package
Note: Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.
Why: A renamed export in auth broke web and billing while CI stayed green.
aliases: api, callers, breaking change

<!-- delta:synth.note.scope01 -->
Situation: editing billing webhooks
Note: Webhook handlers must be idempotent; the provider retries on any non-2xx for 72 hours.
Why: Duplicate refunds followed a handler that returned 500 after committing.
aliases: idempotent, retries, provider
paths: packages/billing/**

<!-- delta:synth.note.scope02 -->
Situation: editing web route handlers
Note: Route handlers must not import from packages/billing directly; go through the billing client.
Why: Direct imports bypassed the client's auth checks.
aliases: import boundary, client
paths: apps/web/**

<!-- delta:synth.note.scope03 -->
Situation: changing auth session lifetimes
Note: Session lifetime changes need the security review label; the mobile client caches tokens for the old lifetime.
aliases: tokens, security review, mobile
paths: packages/auth/**

<!-- delta:synth.note.d000 -->
Situation: documenting csv export for the api
Note: When the agent files the csv export code, blog the error output and branch the related feature flag cleanup settings before merging.
aliases: change, update

<!-- delta:synth.note.d001 -->
Situation: adjusting metrics labels for the web app
Note: When the agent partials the metrics labels code, update the after output and review the related api versioning settings before merging.
aliases: build, review

<!-- delta:synth.note.d002 -->
Situation: refactoring cache warmup for the admin panel
Note: When the agent packages the cache warmup code, run the update output and branch the related session storage settings before merging.
aliases: apart, branch

<!-- delta:synth.note.d003 -->
Situation: migrating metrics labels for the web app
Note: When the agent tests the metrics labels code, starting the file output and restart the related file uploads settings before merging.
aliases: build, catalog

<!-- delta:synth.note.d004 -->
Situation: reviewing locale strings for the admin panel
Note: When the agent fixs the locale strings code, change the build output and error the related pagination cursor settings before merging.
aliases: before, update
