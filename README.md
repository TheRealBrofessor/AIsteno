# AIsteno

AIsteno is a local, reversible shorthand layer for compressing Miahou-style
agent memory and session text. Version 0.1 is deliberately conservative:
evidence-like text is left visible and unchanged, and every supported
substitution roundtrips exactly.

## Install

```sh
python -m pip install -e .
```

## Safety model

- `encode` and `decode` are previews by default, even when `--out` is given.
- Add `--apply` to create the output file.
- Existing output files and input files are never overwritten.
- Paths, hashes, case references, dates/timestamps, commands, error strings,
  device details, and legal/forensic lines are excluded from compression.
- AIsteno never reads or writes Miahou configuration or memory directories on
  its own; it only handles the input path explicitly supplied to it.

## Usage

```sh
# Preview the encoded result; writes nothing
aisteno encode examples/miahou_memory_sample.md --out /tmp/memory.aisteno

# Explicitly create a new output file
aisteno encode examples/miahou_memory_sample.md \
  --out /tmp/memory.aisteno --apply

# Preview or explicitly write a decoded file
aisteno decode /tmp/memory.aisteno --out /tmp/memory.decoded.md
aisteno decode /tmp/memory.aisteno \
  --out /tmp/memory.decoded.md --apply

aisteno preview examples/session_sample.md
aisteno stats examples/session_sample.md
aisteno roundtrip examples/session_sample.md
```

The complete command set is:

```text
aisteno encode INPUT --out OUTPUT [--apply]
aisteno decode INPUT --out OUTPUT [--apply]
aisteno preview INPUT
aisteno stats INPUT
aisteno roundtrip INPUT
```

`preview` displays an encoding without writing it. `stats` reports original
and encoded character counts, savings, reduction percentage, and roundtrip
status. `roundtrip` exits nonzero if decoding the encoded form differs from the
input.

## Format

Encoded files begin with the fixed `AISTENO/v0.1` reversible header and legend.
The body follows a `BODY:` marker. A literal shorthand collision is prefixed by
`~`, and a literal `~` is encoded as `~~`; decoding removes those escapes. This
makes inputs that already contain strings such as `AN` or `BK` unambiguous.

## Development

```sh
python -m unittest discover -s tests -v
```
