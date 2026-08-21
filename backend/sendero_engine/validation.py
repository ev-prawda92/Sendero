"""
Selection-bias deflation for Sendero classifications.

Ported in spirit (not formula) from NWC Quant's deflated Sharpe ratio
(nwc_quant/validation.py, implementing Lopez de Prado 2014). The idea that
transplants: if you tried N things before landing on the one you're
reporting, the best of N noisy draws looks better than reality by a
predictable amount -- and that amount grows with N.

For Sendero, "trying N things" means running classify() against N different
cohort-column combinations, or N different metric choices, on the SAME
underlying data, hunting for the cleanest BUILD/TRAINING signal. That's
exactly the multiple-comparisons trap deflated Sharpe exists to catch in
quant strategy backtests -- an analyst (or an automated sweep) trying every
plausible cohort split until one looks decisive is the same failure mode as
a quant trying every plausible factor combination until one backtests well.

The method differs from NWC Quant's because Sendero doesn't have a returns
time series to compute an analytic Sharpe-estimator variance from. Instead
this uses a permutation test: shuffle the metric column N times (destroying
any real relationship between performance and the cohorts), classify() each
shuffle, and see how often chance ALONE produces a build/training strength
as extreme as the real result. That empirical null distribution plays the
same role NWC Quant's `_expected_max_sharpe` plays analytically -- both
answer "how good would the best of N noisy trials look, even if there were
no real effect?"
"""
import random

from .classify import classify


def permutation_null(rows, metric, baseline=None, higher_is_worse=True,
                      capability_cols=None, config_cols=None,
                      n_permutations=200, seed=42):
    """
    Runs classify() n_permutations times on the same rows with the metric
    column shuffled, so any real relationship between performance and the
    cohort columns is destroyed. The resulting distribution of build/training
    strength is what chance alone produces for THIS data shape (same n,
    same cohort cardinalities) -- the null Sendero's real result gets
    compared against.
    """
    rng = random.Random(seed)
    values = [r.get(metric) for r in rows]
    null_strengths = []
    null_confidences = []
    for _ in range(n_permutations):
        shuffled = values[:]
        rng.shuffle(shuffled)
        perm_rows = [dict(r) for r in rows]
        for r, v in zip(perm_rows, shuffled):
            r[metric] = v
        result = classify(perm_rows, metric, baseline, higher_is_worse,
                           capability_cols, config_cols)
        if "error" not in result:
            null_strengths.append(max(result["build_score"], result["training_score"]))
            null_confidences.append(result["confidence_pct"])
    return {
        "n_permutations": len(null_strengths),
        "null_strengths": null_strengths,
        "null_confidences": null_confidences,
    }


def deflate(observed_result, null, n_trials_tried=1):
    """
    observed_result: the real classify() output being reported (from the
        actual, un-shuffled data).
    null: output of permutation_null() run on the SAME rows/metric/cohorts.
    n_trials_tried: how many different cohort-column or metric combinations
        were actually tried before landing on this reported result. This is
        the caller's honesty check -- if an analyst tried 8 different cohort
        splits and is reporting the best-looking one, n_trials_tried=8 is
        what makes the deflation meaningful. Defaults to 1 (no search).

    Mirrors deflated_sharpe's structure: a "would the best of N null draws
    reach this observed strength by chance" probability, used to haircut the
    reported confidence rather than take it at face value.
    """
    obs_strength = max(observed_result["build_score"], observed_result["training_score"])
    null_strengths = sorted(null["null_strengths"])
    n = len(null_strengths)
    if n == 0:
        return {"error": "No valid permutations -- check the data has enough rows."}

    # Empirical p-value: fraction of single null draws at or above what was observed.
    p_single = sum(1 for s in null_strengths if s >= obs_strength) / n

    # Probability that the BEST of n_trials_tried draws from this null would
    # reach the observed strength by chance -- the direct analog of
    # NWC Quant's "expected max Sharpe of N iid trials under the null".
    p_max_of_n = 1 - (1 - p_single) ** max(n_trials_tried, 1)

    deflated_confidence = round(observed_result["confidence_pct"] * (1 - p_max_of_n))

    passes = p_max_of_n < 0.05
    return {
        "observed_strength": round(obs_strength, 3),
        "null_p_single_trial": round(p_single, 4),
        "null_p_after_n_trials": round(p_max_of_n, 4),
        "n_trials_assumed": n_trials_tried,
        "reported_confidence_pct": observed_result["confidence_pct"],
        "deflated_confidence_pct": deflated_confidence,
        "passes_0.95_bar": passes,
        "verdict": (
            "HOLDS -- unlikely to be a fluke of cohort-hunting, even accounting "
            "for how many splits were tried."
            if passes else
            "CAUTION -- plausibly what chance alone would produce given how many "
            "cohort combinations were tried. Treat as directional, not decisive; "
            "narrow the cohort search or gather more data before acting on it."
        ),
    }
