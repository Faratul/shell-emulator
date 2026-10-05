#!/usr/bin/env bash
# VFS: минимальный (один файл)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nvfs-dump hello.txt\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/minimal.zip" --script "$TMP"
rm -f "$TMP"
