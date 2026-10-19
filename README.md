# LeanLoop development bootstrap

LeanLoop is the team's cost-aware Agent harness project for PE6203 Project 5.
This folder is a local bootstrap until the team creates its shared private GitHub repository.

## Local prerequisites

- Python 3.12 or newer
- `uv`
- Docker Desktop running
- An OpenRouter API key only when running a real model

On this Mac, Docker Desktop's CLI lives at:

```text
/Applications/Docker.app/Contents/Resources/bin
```

For the current terminal session, run:

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

## Safe checks (no model cost)

```bash
/opt/homebrew/bin/python3.12 scripts/doctor.py
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker run --rm hello-world
```

## TUA-Bench bootstrap

```bash
cd vendor/TUA-Bench
/opt/homebrew/bin/uv sync
/opt/homebrew/bin/uv run setup-env
```

`setup-env` downloads benchmark assets. Do not run a benchmark command until the
team agrees on the model, task subset, cost cap, and provider key.

## Secret handling

Copy `.env.example` to `.env` and fill in the API key locally. Do not send the
key in chat or commit it to GitHub.
