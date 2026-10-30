# Installation and Reproduction

## Integration prerequisites

Integrate the selected files under `repo_files/` into the current team repository while preserving its latest root README, project/dependency files, and other members' work. The shared `mini_base.yaml` and canonical 40-task list are already under `contributions/liu-yalin/developer_pack/settings`. Copies in this contribution's audit directory are references for hash checking, not replacements for the shared files.

Use the pinned team environment: TUA-Bench commit `3497fd320abcafaf4797424192c891a593fd7964`, Harbor 0.6.3, and mini-swe-agent 2.4.3. The Python interpreter at `vendor/TUA-Bench/.venv/bin/python` must be able to import Harbor. Provider credentials must be configured privately by the operator and must not be committed. This package excludes vendor environments, virtual environments, Docker images, and uv caches.

## Offline tests

From the team repository root, run the tests without model calls:

```bash
vendor/TUA-Bench/.venv/bin/python -B -m unittest discover -s tests -p 'test_context_*.py' -v
```

The tests use the repository's existing `contributions/liu-yalin/developer_pack/examples/c0_single_task` fixture. This fixture is attributed to the shared developer pack and is not a new formal C0 experiment.

## Harbor adapter

Apply the reversible local adapter patch and select the experimental platform:

```bash
vendor/TUA-Bench/.venv/bin/python scripts/manage_context_harbor_adapter.py apply
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

## Command preview

These commands preview reproduction with the frozen settings. They do not invoke a model by default:

```bash
vendor/TUA-Bench/.venv/bin/python scripts/run_context_batch.py --configuration A --suite formal --tua-root vendor/TUA-Bench --model openrouter/minimax/minimax-m3.1-flash --cost-limit 0.06 --uv uv --run-root runs/context-reproduction --record-root results/context-reproduction
vendor/TUA-Bench/.venv/bin/python scripts/run_context_batch.py --configuration B --suite formal --tua-root vendor/TUA-Bench --model openrouter/minimax/minimax-m3.1-flash --cost-limit 0.06 --uv uv --run-root runs/context-reproduction --record-root results/context-reproduction
```

A paid repetition requires separate operator authorization and `--live`. Use fresh output directories and do not overwrite the submitted formal records. No repetition is needed to inspect or merge the existing results.

## Actual launcher history

The original `scripts/run_context_batch.py` stops a batch on exceptions or excess cost. Later B runs used the archived wrappers under `audit/historical-launchers`: completed tasks were skipped, failed attempts were preserved, and authorized queues continued. Batch provenance includes infrastructure settings and hashes.

The archived wrappers contain original local paths and depend on assets that are not bundled, including uv caches. They are audit material rather than portable one-command launchers. Port the root, assets, and proxy settings before any separately authorized reproduction. Agent/model policy and A/B context settings remained frozen during the submitted experiments.

Delivery-copy translations of launcher messages are identified in the historical-launcher README. Execution-time fingerprints refer to the original artifacts. Infrastructure fixes concerned dependency installation and transport, not scoring logic. The original trial manifests and `audit/run-provenance` contain the actual execution commands.
