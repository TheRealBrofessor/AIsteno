# AIsteno roadmap

AIsteno v0.4 has a working core engine: archive encoding, pack-mode memory
compression, pack statistics, and redacted secret scanning.

The next product milestone is plug-and-play agent installation.

## v0.5 target

### Agent-agnostic commands

```sh
aisteno init
aisteno pack-dir ./memory --out ./memory/packed
aisteno watch ./memory
aisteno verify ./memory/packed
aisteno redact-check ./memory
```

### Adapter commands

```sh
aisteno install-adapter generic
aisteno install-adapter miahou
```

The generic adapter should work with any text-file memory layout by asking for:

```text
source memory path
packed output directory
budget limit
secret policy
refresh mode: manual, watch, or pre-start hook
```

## Design rules

- AIsteno remains agent-agnostic.
- Full memory remains the source of truth.
- Packed memory is a derived injection snapshot.
- Secrets are never printed in reports.
- Writes require explicit apply-style behavior.
- Archive mode stays reversible and exact.
- Pack mode stays lossy, compact, and prompt-oriented.

## Minimum plug-and-play success state

A new user should be able to run:

```sh
pipx install git+https://github.com/TheRealBrofessor/AIsteno.git
aisteno init
aisteno pack-dir ./memory --out ./memory/packed
```

Then point any agent at the generated packed files for prompt injection.
