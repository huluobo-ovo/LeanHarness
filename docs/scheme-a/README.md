# Role 2: Context Management

This contribution provides two independent single-change candidates: A (current-output shaping) and B (old-history compaction), each evaluated on the same 40 formal tasks. The team-agreed scope is to select one candidate as the final method. The comparison is shared C0 versus A and shared C0 versus B. These materials provide code, experimental results, and reproducibility evidence.

## Method

A enables only `output_shaping`. B enables only `history_compaction`. Both are deterministic transformations that add no LLM calls and preserve the model, decoding settings, tasks, and verifiers. The original outputs remain available. B shortens older observations in the request copy. See `adapters/context_runtime_agent.py`, `configs/context-A.yaml`, and `configs/context-B.yaml`.

## Fixed setup

- Model: `openrouter/minimax/minimax-m3.1-flash`.
- TUA-Bench commit: `3497fd320abcafaf4797424192c891a593fd7964`.
- Harbor 0.6.3 and mini-swe-agent 2.4.3.
- 30 agent steps, 900-second agent time limit, and `linux/amd64` containers. Image building and installation are outside the agent time limit.
- Cost parameter: USD 0.06 per task. This was a soft limit with post-trial auditing, not a guaranteed hard cutoff during a model call. Over-budget outcomes are preserved and disclosed.

## Results

The primary metric is mean reward, including partial credit. Full-credit rate is reported separately.

| Candidate | Final tasks | Mean reward | Full-credit tasks | Final-task response cost (USD) |
| --- | ---: | ---: | ---: | ---: |
| A | 40 | 45.384388% | 17 | 0.886041360 |
| B | 40 | 47.761559% | 18 | 1.301179545 |

Both groups have 40 completed final records. Valid reward-zero outcomes are retained. An earlier interrupted B task 066 incurred another USD 0.05411265. Known B response spending including that attempt is at least USD 1.355292195. See `results/context-formal/cost-accounting.json` for cost scope and exceptions.

## Files for analysis

Under `results/context-formal/`:

- `formal-A-final40.csv` and `formal-B-final40.csv`: one final record per task and candidate.
- `formal-A-all-attempts.csv`, `formal-B-all-attempts.csv`, and `attempt-ledger.csv`: preserved attempts, including infrastructure failures.
- `Role2_Experiment_Data_Collection.xlsx`: 80 final records, configuration descriptions, and formula-based summaries. `Full credit (1/0)` means reward equals 1. `Actual reward` preserves partial credit.
- `summary-A-B.csv` and `paired-A-B.csv`: aggregate and paired A/B data.
- `comparison-C0-A-B.csv`, `paired-C0-A-B.csv`, and `C0-reference-provenance.json`: comparison with the teammate-supplied C0 baseline.

Final rewards and response costs were cross-checked against all 80 final trajectories and verifier results. The 21 context-related offline tests passed. `DATA_DICTIONARY.md` defines the metrics and cost accounting; `REPRODUCE.md` describes installation and reproduction.

## Evidence access

Raw trial artifacts are supplied separately as `Role2_Raw_Evidence_RESTRICTED_DRIVE.zip`. They are excluded from the source repository. Evidence link: **TO BE ADDED BY THE REPOSITORY MAINTAINER**. The maintainer must ensure that the instructor and teaching assistants can access it.

`raw-artifact-manifest.csv` records original local hashes. `delivery-evidence-manifest.csv` records hashes of the credential-redacted delivery copies and should be used to verify the evidence archive. Some captured trajectories contained credential-like strings; the delivery copies were redacted and the local originals were not modified. See `security-redactions.json`.

## Interpretation and scope

There is one formal outcome per task and candidate; these results do not establish statistical significance. Shared C0 mean reward is 48.0307%. Its reported cost uses a key/account usage delta including retries, which differs from the final-task response-cost scope above. Cost/Pareto claims require reconciliation of those scopes. C1 was handed off to another computer; incomplete local C1 results are not presented as a completed baseline.

The shared baseline is attributed to its teammate author. This contribution does not claim authorship of another member's experiments. The group analysis owner integrates the final baseline comparison, cross-method accuracy-cost/Pareto plots, failure analysis, report, and presentation using the supplied data.
