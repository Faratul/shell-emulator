#!/usr/bin/env bash
# VFS: 3+ уровня вложенности
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nvfs-dump /home/user/docs/archive/2024/log.txt\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/deep.b64" --script "$TMP"
rm -f "$TMP"
