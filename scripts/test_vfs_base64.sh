#!/usr/bin/env bash
# VFS: ZIP в виде base64-текста
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/deep.b64" --script "$TMP"
rm -f "$TMP"
