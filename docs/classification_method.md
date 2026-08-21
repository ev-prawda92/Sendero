# Sendero Classification Method (Reference)

This is the interpretation guide for the two-level outlier test in
`scripts/classify.py`. Read it before explaining a result to a client.

## The core idea

Every friction point in a complex system is either a **systematic** problem
(the build/configuration is wrong, dragging everyone) or an **individual**
problem (the system is fine, some users haven't adopted it) — or a mix. These
need opposite remediations and opposite budget owners. Sendero separates them
statistically instead of by opinion.

## Level 1 — Dispersion + Elevation ("is everyone equally affected?")

Sendero looks at the *shape* of the per-user distribution:

- **Coefficient of variation (CV = std/mean).** Low CV means everyone performs
  similarly — a uniform drag, which points to a **build** problem. High CV means
  a wide spread — some fine, some struggling — which points to **training**.
- **Outlier tail share.** Using a robust median + MAD fence, Sendero measures how
  much of the population is a genuine outlier over the healthy body. A distinct
  tail is a **training** signature (a minority of strugglers).
- **Body elevation.** How far the *median* (immune to the tail) sits from
  baseline. A global misconfiguration raises the floor for *everyone* — including
  your best users — without creating cohort-explained variance. That elevated
  floor is the one build fingerprint a uniform config problem leaves behind, so
  Sendero treats it as an independent build signal. This is what lets true
  hybrids surface instead of collapsing to one side.

## Level 2 — Explanatory power ("what explains the spread?")

Sendero computes **eta-squared** (the fraction of total variance explained) for
each cohort you provide:

- If a **capability cohort** (tenure, experience, training-completed) explains the
  spread, the strugglers cluster by skill → **TRAINING**.
- If a **configuration cohort** (department, module, site, workflow, order type)
  explains the spread **and each group is internally uniform**, then specific
  configurations are broken → **BUILD**. (Internal uniformity matters: if a
  "department" group is itself all over the place, the department label isn't
  really capturing a config difference.)

Level 2 is weighted more heavily when it has real explanatory power and more
lightly when no cohort explains much — in which case Sendero leans on Level 1.

## Reading the score

- `build_score ≥ 0.66` → **BUILD** 🔴
- `build_score ≤ 0.34` → **TRAINING** 🟢
- in between → **HYBRID** 🟡

`confidence_pct` rises when the two levels agree and Level 2 has power. A HYBRID
with the two levels pulling apart is a *real* finding — say so: "the system is
uniformly slow (a build floor) AND newer users are slower still (an adoption
gap); fix the config first, then measure the residual."

## Honest limitations (say these out loud)

- **Correlation, not proof.** Sendero points you at the likely owner; a build
  engineer or trainer still confirms root cause. It replaces guesswork, not
  judgment.
- **Cohorts must be meaningful.** Garbage or missing cohort columns weaken
  Level 2. The metric-only mode still works but is less decisive.
- **One friction point at a time.** Each metric column is a separate diagnosis.
  Don't average unrelated frictions together.
- **Baseline matters.** Without a `--baseline`, the elevation signal is off and
  hybrids are harder to see. Get the pre-change/target number if you can.
- **Small samples are noisy.** Under ~20 users, treat results as directional.

## Suggested defaults by metric type

| Metric | Direction | Typical baseline source |
|---|---|---|
| Minutes per task | higher is worse | pre-go-live time / vendor benchmark |
| Error / rejection rate | higher is worse | target SLA (e.g. <1%) |
| Clicks or steps | higher is worse | designed happy-path count |
| Throughput per hour | lower is worse | pre-change throughput |
| Adoption / usage rate | lower is worse | rollout target |
