#!/usr/bin/env sh
set -eu

if command -v pipx >/dev/null 2>&1; then
  exec pipx install "git+https://github.com/TheRealBrofessor/AIsteno.git"
fi

if command -v python3 >/dev/null 2>&1; then
  echo "pipx is recommended for isolated CLI installation." >&2
  exec python3 -m pip install --user "git+https://github.com/TheRealBrofessor/AIsteno.git"
fi

echo "AIsteno requires Python 3.10+ and pipx or pip." >&2
exit 1
