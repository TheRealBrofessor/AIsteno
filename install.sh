#!/usr/bin/env sh
set -eu

if command -v pipx >/dev/null 2>&1; then
  exec pipx install "git+https://github.com/TheRealBrofessor/AIsteno.git@master"
fi

if command -v python3 >/dev/null 2>&1; then
  install_root="${XDG_DATA_HOME:-$HOME/.local/share}/aisteno"
  python3 -m venv "$install_root/venv"
  "$install_root/venv/bin/python" -m pip install --upgrade "git+https://github.com/TheRealBrofessor/AIsteno.git@master"
  mkdir -p "${XDG_BIN_HOME:-$HOME/.local/bin}"
  ln -sf "$install_root/venv/bin/aisteno" "${XDG_BIN_HOME:-$HOME/.local/bin}/aisteno"
  echo "installed AIsteno; ensure ${XDG_BIN_HOME:-$HOME/.local/bin} is on PATH" >&2
  exit 0
fi

echo "AIsteno requires Python 3.10+ and pipx or pip." >&2
exit 1
