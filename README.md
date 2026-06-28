# AIsteno

AIsteno is a universal packed-memory layer for AI agents.

It keeps an agent's full memory file editable, then creates a compact, redacted,
prompt-ready snapshot that can be injected into a system prompt, context block,
or retrieval preamble. It is not tied to one agent framework.

Use it with any local or custom agent that stores memory as text: Codex-style
agents, Claude Code-style workflows, LangGraph, AutoGen, CrewAI, OpenHands,
Miahou, or a plain Python agent.

## What it does

AIsteno has three deliberately separate modes:

- **Pack**: lossy, fact-preserving memory compression for prompt injection.
- **Secret scan**: reports likely secrets without printing the raw values.
- **Archive**: exact reversible shorthand storage for cases where byte-for-byte
  recovery matters.

For agent memory injection, use **pack mode**, not archive mode.

## Install

From a local checkout:

```sh
python3 -m pip install -e .
```

With `pipx` from GitHub after the repository is public:

```sh
pipx install git+https://github.com/TheRealBrofessor/AIsteno.git
```

## Quick start

Preview a packed memory snapshot without writing anything:

```sh
aisteno pack-preview ./MEMORY.md
```

Write a packed memory file explicitly:

```sh
aisteno pack ./MEMORY.md --out ./packed/MEMORY.packed.md --apply
```

Replace an existing packed output only when intentional:

```sh
aisteno pack ./MEMORY.md --out ./packed/MEMORY.packed.md --apply --force
```

Check reduction and warning counts:

```sh
aisteno pack-stats ./MEMORY.md
```

Scan for likely secrets without printing secret values:

```sh
aisteno secret-scan ./MEMORY.md
```

## Agent integration pattern

AIsteno does not need to own your agent. The clean integration is:

```text
agent writes full memory -> AIsteno packs it -> agent injects packed memory
```

Recommended layout:

```text
memory/
  MEMORY.md              # full editable memory
  USER.md                # full editable user profile
  packed/
    MEMORY.packed.md     # prompt injection snapshot
    USER.packed.md       # prompt injection snapshot
```

The agent should continue writing to the full memory files. Regenerate the packed
files after memory edits, then inject only the packed files into the prompt.

## Safety model

- Transforming commands are dry-run by default.
- `--apply` is required to write an output file.
- `--apply --force` is required to replace an existing output file.
- The input file is never overwritten.
- Pack mode redacts likely passwords, sudo values, API keys, access tokens,
  generic secrets, login credentials, and conservative password-like values.
- `secret-scan` reports counts, line numbers, types, and redacted previews only.
- Archive mode is exact and intentionally does **not** redact; do not inject
  archive output as agent memory.

## Output shape

Default packed output has no header or legend. It uses compact domain records,
for example:

```text
PREF{ans=concise/direct;cmd=1box;no=fluff}
DEV{primary=Linux workstation;OS=Ubuntu}
WF{dry.first;bk.pre.edit;git.ckpt}
SECRET{type=password;stored=no}
```

Optional legend:

```sh
aisteno pack-preview ./MEMORY.md --legend
```

## Current CLI

```text
aisteno pack INPUT [--out OUTPUT] [--apply] [--force] [--legend]
aisteno pack-preview INPUT [--legend]
aisteno pack-stats INPUT
aisteno secret-scan INPUT
aisteno encode INPUT --out OUTPUT [--apply] [--force]
aisteno decode INPUT --out OUTPUT [--apply] [--force]
aisteno preview INPUT
aisteno stats INPUT
aisteno roundtrip INPUT
```

## Roadmap

The core engine is usable now. Plug-and-play agent installs should come next:

```text
aisteno init
aisteno pack-dir ./memory --out ./memory/packed
aisteno watch ./memory
aisteno install-adapter generic
aisteno install-adapter miahou
```

Those commands are roadmap items unless implemented in the current CLI.

## Development

The test suite uses the Python standard library:

```sh
python3 -m unittest discover -s tests -v
```

If pytest is installed:

```sh
pytest -q
```
