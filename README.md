# LeanHarness: Cost-Aware Agent Harness Optimization

This repository is the team codebase for PE6203 Project 5. The project asks whether an AI agent can complete TUA-Bench tasks more reliably and efficiently by improving its tool-use channel, while keeping the **tasks, model, and budget identical**.

The current implementation uses mini-SWE-agent and runs TUA-Bench through Harbor. Role 5 (the tool-interface layer) provides three formal configurations:

- **T1 / Result Normalizer**: converts inconsistent tool outputs into a short, consistent, readable format.
- **T2 / Result Normalizer + Command Guard**: builds on T1 by checking and providing guidance for unsafe, repeated, or malformed commands.
- **T3 / Command Guard**: enables Command Guard only, isolating the guard from Result Normalizer.

For the detailed flow of “AI agent issues a command → tool layer processes it → environment returns a result,” see the [tool-interface map](docs/tool-interface-map.md) and [Harbor integration guide](docs/role5-harbor-integration.md).

## Shared Experimental Settings

| Item | Shared setting |
| --- | --- |
| Benchmark | TUA-Bench (pinned commit: `3497fd320abcafaf4797424192c891a593fd7964`) |
| Runtime stack | Harbor `0.6.3`, mini-SWE-agent `2.4.3`, Python `3.12.15` |
| Formal tasks | The fixed 40 tasks in `configs/task_list_40.txt` |
| Formal configurations | Same task set, at most 30 steps, and at most 900 seconds per task |
| Budget for the inexpensive model | At most USD 0.06 per task |
| Team budget | USD 35 target and USD 40 hard limit |

In formal experiments, each configuration runs each task once. Zero-reward runs and ordinary failures must be retained. A rerun is allowed only for a confirmed infrastructure failure, and its reason must be recorded. Never commit API keys or run `harbor upload`.

## Quick Start

### 1. Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop (running)
- An OpenRouter API key (required only for real model runs)

On macOS, if the terminal cannot find the Docker CLI:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

### 2. Configure a Local API Key

```bash
cp .env.example .env
```

Then add your own `OPENROUTER_API_KEY` to `.env`. The file is ignored by Git and must never be committed or shared with teammates.

### 3. No-Cost Checks

```bash
/opt/homebrew/bin/python3.12 scripts/doctor.py
docker run --rm hello-world
/opt/homebrew/bin/uv run --group dev pytest
```

The unit tests use fake executors and do not call OpenRouter, run a Docker task container, or incur model cost.

### 4. Initialize TUA-Bench

```bash
cd vendor/TUA-Bench
/opt/homebrew/bin/uv sync
/opt/homebrew/bin/uv run setup-env
cd ../..
```

`setup-env` downloads benchmark assets. Before the first formal run, follow the [experiment guide](docs/role5-experiment-guide.md) to validate one task and confirm that Harbor Exceptions is 0.

## Role 5 Configurations and Runs

| Configuration ID | File | Purpose |
| --- | --- | --- |
| T1 | `configs/tool-interface-normalizer.yaml` | Enables Result Normalizer only |
| T2 | `configs/tool-interface-complete.yaml` | Enables both Result Normalizer and Command Guard |
| T3 | `configs/tool-interface-command-guard.yaml` | Enables Command Guard only |

The sequential batch launcher is `scripts/run_role5_batch.py`. It runs tasks one at a time in a fixed order, writes local results, and sets the `linux/amd64` Docker platform required by Apple Silicon. Example:

```bash
/opt/homebrew/bin/uv run python scripts/run_role5_batch.py \
  --configuration T1 \
  --task 000-count-nuclei \
  --task 003-rebuild-energy-model
```

Repeat `--task <task-ID>` in the order listed in `configs/task_list_40.txt` to form a sequential batch. Before running, read the [experiment guide](docs/role5-experiment-guide.md) and confirm the model, budget, output directory, and recovery rules. Do not launch the same batch concurrently or overwrite existing formal results with a new run.

## Results, Cost, and Analysis

- Local formal results are stored in `results/role5/formal-results.csv`; raw run artifacts are stored in `runs/role5-formal/`. Neither should be submitted to GitHub.
- Record at least the task ID, configuration ID, model, reward, exception status, runtime, tokens, and actual cost for every task.
- Harbor may report OpenRouter cost as `0.0`; check OpenRouter cumulative usage before and after a formal batch and use the difference to verify the actual cost.
- The analysis rules and four core metrics are defined in the [Role 5 analysis protocol](docs/role5-analysis-protocol.md).

## Directory Guide

```text
adapters/       Reproducible Harbor and mini-SWE-agent integration code
configs/        T1/T2/T3 configurations, formal task list, and development tasks
docs/           Experiment, integration, results-recording, and analysis documents
scripts/        Environment checks, configuration validation, run, and analysis scripts
src/            LeanHarness tool-interface implementation
tests/          Unit tests that do not incur model cost
templates/      Results-recording templates
contributions/  Original member-submission archives (not runtime dependencies)
vendor/         Upstream third-party snapshots; do not modify their README files
```

## Deliverables for Members 2–5

Members may use a free model for single-task development without waiting for shared C0/C1 results. Formal experiment configurations should reflect the structure of the proposed method:

1. If there are two independently enabled components, A and B, submit A-only, B-only, and A+B configurations, and analyze each component’s contribution.
2. If there is one indivisible change, submit only A and compare it with shared C0; do not create a meaningless ablation merely to increase the number of configurations.
3. If a single change still contains a key internal component, submit the complete version and an ablation with that component disabled.

Each member must also submit the change and hypothesis, configuration IDs, exact run commands, full results for the 40 tasks, raw logs/trajectories, and a comparative analysis against C0 and their own ablations.

## Handling Archived README Files

This root README is the project’s main entry point. `contributions/liu-yalin/README.md` and `developer_pack/README_zh.md` are directory-level descriptions for archived material. They are retained to preserve the provenance and original context of the submission; they do not duplicate this project README and are not runtime instructions. README files under `vendor/` belong to upstream dependencies and remain unchanged.
