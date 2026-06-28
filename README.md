# AIsteno

AIsteno is a local memory compressor for Miahou-style agents. Version 0.4 has
three deliberately distinct modes:

- **Archive:** exact, reversible storage through `encode`, `decode`, and
  `roundtrip`. Its format header means short inputs may grow.
- **Inject:** compact reversible phrase shorthand through `preview` and the
  archive encoder.
- **Pack:** lossy, fact-preserving structured memory summaries designed for
  normal preferences, projects, devices, tools, workflows, and tasks.

Pack output is not byte-reversible. Use archive mode when exact text matters.
Pack mode always scans and redacts likely secrets before any compression.

## Install

```sh
python3 -m pip install -e .
```

## Pack normal memory

```sh
# Both print packed text and write nothing
aisteno pack examples/normal_user_memory_sample.md
aisteno pack-preview examples/normal_user_memory_sample.md

# Show reduction and warning counts
aisteno pack-stats examples/normal_user_memory_sample.md

# Scan without printing secret values
aisteno secret-scan examples/normal_user_memory_sample.md

# Still a dry run: OUTPUT is not created
aisteno pack examples/normal_user_memory_sample.md --out /tmp/user.pack

# Explicitly create a new output
aisteno pack examples/normal_user_memory_sample.md \
  --out /tmp/user.pack --apply

# Replacing an existing output requires both flags
aisteno pack examples/normal_user_memory_sample.md \
  --out /tmp/user.pack --apply --force

# Include the optional tag legend
aisteno pack-preview examples/normal_user_memory_sample.md --legend
```

Default packed output has no header or legend. It uses one structured line per
record category, such as:

```text
PREF{ans=concise/direct;cmd=1box;no=fluff}
DEV{primary=Lenovo ThinkPad X1 Carbon;OS=Linux}
WF{dry.first;bk.pre.edit;git.ckpt}
SECRET{type=password;stored=no}
```

The packer preserves clear identifiers—including paths, URLs, emails,
hostnames, dates, command snippets, device model names, and app/project
names—while removing grammar and merging duplicate facts. Legal, device,
account, project, tool, status, risk, path, and workflow facts are kept in
separate domain records where possible. The categorized
normal-memory vocabulary contains more than 300 mappings.

### Secret handling

`pack`, `pack-preview`, and `pack-stats` detect labeled passwords, sudo values,
API keys, access tokens, generic secrets, login credentials, and conservative
password-like values. Secret values are removed before parsing. Packed output
contains metadata such as `SECRET{type=sudo;stored=no}` but never the value.

`secret-scan` reports only the count, line number, type, and a fully redacted
preview. Archive mode intentionally remains exact and does not redact; do not
inject archive output as agent memory.

Pack mode also coarsens privilege behavior: full-permission hints become
`priv=high`, and password-handling hints become
`secret.policy=do_not_store`. Operational sudo behavior is not injected.

## Archive mode

```sh
# Preview only, even though --out is supplied
aisteno encode examples/miahou_memory_sample.md --out /tmp/memory.aisteno

# Create a new archive explicitly
aisteno encode examples/miahou_memory_sample.md \
  --out /tmp/memory.aisteno --apply

aisteno decode /tmp/memory.aisteno --out /tmp/memory.decoded.md --apply
aisteno preview examples/session_sample.md
aisteno stats examples/session_sample.md
aisteno roundtrip examples/session_sample.md
```

Archive files start with `AISTENO/v0.1`; retaining the v0.1 format identifier
keeps existing archives compatible. Literal shorthand collisions and tildes
are escaped so archive decoding restores the original text exactly, including
line endings.

## Safety

- Transforming commands default to preview/dry-run.
- `--apply` is required to write; `--apply --force` is required to replace an
  existing output.
- The input path is never overwritten, even with `--force`.
- AIsteno only reads the input explicitly supplied to a command and never
  discovers or edits Miahou memory on its own.

## Development

The suite has no third-party test dependency:

```sh
python3 -m unittest discover -s tests -v
```

If pytest is installed, the same suite also runs with:

```sh
pytest -q
```
