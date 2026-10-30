# Independent Context-Management Candidates

The team-agreed submission scope comprises two independent single-change candidates, with one selected as the final method. Shared C0 has both context switches disabled. A enables current-output shaping only. B enables old-history compaction only. The three groups use the same 40-task list and MiniMax model, with one formal outcome per task. Valid zero-reward outcomes are retained.

The teammate-supplied `c0_results_40.csv` and `c0_summary.json` establish C0 mean reward of 48.0307%. C0 is a shared baseline and is not claimed as this member's independent experiment. Paired inputs are in `paired-C0-A-B.csv`; aggregate comparisons are in `comparison-C0-A-B.csv`.

| Candidate | Mean reward | Difference from C0 (percentage points) | Task wins | Task losses | Ties |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 45.3844% | -2.6463 | 4 | 4 | 32 |
| B | 47.7616% | -0.2691 | 5 | 4 | 31 |

Neither candidate exceeds C0 in mean reward. The data do not support a claim of improved accuracy. A has lower final-task response cost than the reported C0 amount, but C0 uses a key/account delta including retries. Those scopes do not support a direct audited cost-reduction percentage. B's final-task response cost exceeds the reported C0 delta, so there is no demonstrated joint accuracy-and-cost advantage. A single run per group does not establish statistical significance.

Per-task actual C0 costs are unavailable and are not filled with zero. The group analysis owner must reconcile complete base settings, decoding, environment, and cost scopes before cross-method comparisons. This contribution supplies its own frozen settings and trajectory/command evidence.

Use mean reward as the primary accuracy axis, with full-credit rate as an auxiliary metric. Input token counts already include the cached subset. The group analysis owner integrates the cross-method accuracy-cost/Pareto figures, failure cases, report, and presentation from these inputs. This file records component-comparison facts and does not replace those final group deliverables.
