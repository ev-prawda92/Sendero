# MVP Roadmap

This lays out what's real today, what's next, and why the order is what it is — useful for a design partner conversation, a hire, or an investor asking "how far along is this, really."

## Slice 0 — done, in this repo

Upload a CSV of portfolio companies (or any per-unit dataset with a performance metric and cohort columns) and get back a real, computed Sendero classification: BUILD, TRAINING, or HYBRID, with a confidence score and the underlying statistical evidence. Results persist and roll up into a worklist ranked by recoverable dollar value. This is the smallest possible proof that the core diagnostic is real and useful, and it deliberately skips everything else so it could be validated with design partners fastest.

**Why start here:** the diagnostic is the differentiated, defensible part of the product — everything else (auth, integrations, AI assistant, collaboration) is well-understood engineering that any competent team can build. Proving the diagnostic is useful on real portfolios, before investing in the rest, is the highest-value use of the first few weeks.

## Slice 1 — auth, seats, and a real hosted deployment

- User accounts and basic role-based access (partner / operating partner / analyst), matching the seats model from the product design.
- Deploy the Flask API + a small persistent Postgres database (swap out SQLite) to a real host — Railway, Render, or Fly.io are the fastest paths for a team this size; a Docker-based deploy to your own infrastructure comes later once there's a reason to control that layer directly.
- Multiple funds/workspaces (multi-tenant), so more than one design partner can use it without seeing each other's data.

## Slice 2 — real data connectors

- Manual CSV/spreadsheet upload stays as the fallback for everything.
- Add one live connector first (QuickBooks Online has the most accessible API for this segment) before attempting NetSuite, Sage Intacct, or others — each is a real, separate integration project, not a generic "connect any accounting system" feature.

## Slice 3 — AI assistant

- Wire the Claude API to answer questions grounded in a fund's own uploaded/connected data (retrieval over what's actually in their workspace, not general web knowledge).
- IC memo drafting as the first concrete assistant task, since it's the clearest, highest-value use case validated in the product design.
- Every AI answer should cite back to the specific data or worklist entry it drew from — this was a deliberate design choice in the mockups and matters a lot for a compliance-conscious buyer.

## Slice 4 — collaboration & storage

- Box integration for exporting/syncing finished memos, rather than building in-house document storage.
- Basic commenting on a memo or worklist entry.
- Full version history is the most expensive item on this list to build well (it's most of what a tool like Google Docs or Notion does) — consider deferring it further, or exporting into a tool a fund already uses for that, rather than building it in-house at all.

## Slice 5 — the differentiated, expensive-to-run features

- Cross-model verification (running a call through more than one model and surfacing agreement/disagreement) for IC-bound, high-stakes classifications only — not routine queries, since it's a real cost driver.
- White-labeling (custom branding, custom domain) once there's a paying customer asking for it specifically.
- **Selection-bias deflation (shipped, opt-in) — `sendero_engine/validation.py`.** Ported in spirit from NWC Quant's deflated Sharpe ratio (López de Prado 2014): if an analyst tried N cohort/metric combinations before landing on the one being reported, the best-looking result is expected to look better than reality by an amount that grows with N. Sendero doesn't have a returns time series for the analytic Sharpe-estimator-variance formula NWC Quant uses, so this uses a permutation test instead — shuffle the metric column, re-run `classify()` many times, and see how often chance alone produces a result this strong. That empirical null plays the same role NWC Quant's expected-max-Sharpe formula plays analytically. Wired into `POST /api/classify` as `validate=true` (plus `n_trials_tried`, the caller's own honesty input on how many splits they actually tried, and `n_permutations`) — off by default because it's real compute a routine classification shouldn't pay for. Covered by tests in `backend/tests/test_app.py`.

## What NOT to build before there's a paying design partner

Don't build a generic "connect any data source" abstraction before you've connected two real ones and seen what's actually different between them. Don't build in-house document collaboration before checking whether "export to Box" satisfies the actual need. Don't build cross-model verification until the single-model diagnostic has been validated as useful on its own — it's a trust-multiplier feature, not a foundational one.
