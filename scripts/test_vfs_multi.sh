#!/usr/bin/env bash
# VFS: несколько файлов, есть двоичный (base64)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nvfs-dump /b.txt\nvfs-dump /image.bin\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/multi.zip" --script "$TMP"
rm -f "$TMP"
