# Data Dictionary and Accounting Rules

## Records and metrics

The primary benchmark success metric is `mean(reward)`, including partial credit. Full-credit rate is `count(reward == 1) / 40`. Positive-reward rate is a different auxiliary metric and must not be substituted for mean reward.

Each `final40` file has 40 rows. The `all-attempts` files preserve distinct run IDs for repeated task IDs. Attempts must not be counted as additional independent tasks or experimental repetitions. Valid reward-zero results are preserved.

The workbook includes 80 final A/B observations. Its `Full credit (1/0)` field is 1 only for reward equal to 1. Its `Actual reward` field is the numeric score used for mean reward. The CSV field names remain the canonical analysis interface.

## Paths and provenance

Original machine-specific absolute paths were converted to project-relative paths in the GitHub CSV copies. The original tables remain in the separate evidence archive. `trial_path` identifies the trial directory, `trajectory_path` identifies the native mini-swe-agent trajectory, and `manifest_path` identifies command and fingerprint evidence.

`source_commit` is the source snapshot recorded at execution time, not a claim that the later upload commit was the experimental revision. The code and configuration SHA-256 fields provide additional execution-time fingerprints.

## Tokens and time

`agent_tokens_in` already includes cached input. `agent_cached_tokens` is a subset and must not be added again. Harness token and dollar fields represent additional harness LLM usage. These transformations make no additional LLM calls, so those fields are zero. Python CPU overhead was not separately measured; total computational overhead is not claimed to be zero.

`wall_time_s` is the full trial wall-clock duration, including environment preparation. It should not be described as model inference time alone. `steps` is the recorded agent step count.

## Actual costs and interrupted attempts

`agent_usd` is the sum of native-trajectory `response.usage.cost` values. Missing costs remain missing and are never zero-filled.

An earlier interrupted B task 066 appears as `missing_result` in the historical CSV. Its preserved trajectory later established 30 calls and USD 0.05411265 of response cost; this is documented separately without rewriting the old CSV. It ended with `LimitsExceeded` and has no formal verifier score. A separately authorized repair attempt subsequently obtained a final reward of zero. The interrupted unscored attempt was not replaced by selecting among valid scored outcomes.

The final-40 costs are USD 0.88604136 for A and USD 1.301179545 for B. Known B spending including the earlier interrupted attempt is at least USD 1.355292195. These are response-cost scopes, not a complete provider invoice.

## Budget exceptions

| Candidate | Task | Actual response cost (USD) |
| --- | --- | ---: |
| A | 117 | 0.08121327 |
| B | 009 | 0.09229728 |
| B | 042 | 0.06191754 |
| B | 066, final attempt | 0.08196102 |
| B | 090 | 0.06194934 |

These outcomes are retained unchanged. The USD 0.06 parameter did not provide a guaranteed in-call hard cutoff. Do not claim that every actual task cost satisfied a strict USD 0.06 cap.

## Infrastructure and artifact integrity

Infrastructure repairs are recorded separately from the frozen agent/model configuration: TLS and HTTPS sources, public CA certificates, proxy transport, uv cache, build tools, OpenFOAM root permissions, and bounded download retries. Relevant records are under `contributions/feng-hao/context-management/audit`. Verifiers were not modified to obtain successful scores.

`raw-artifact-manifest.csv` records original paths, sizes, and SHA-256 hashes. `delivery-evidence-manifest.csv` records redacted delivery hashes and replacement counts. Use the latter to verify the evidence archive. `host.docker.internal:9674` was a local transport setting and is not a portable proxy configuration.
