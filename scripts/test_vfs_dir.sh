#!/usr/bin/env bash
# VFS: передан каталог вместо архива (ошибка)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp)"
printf 'vfs-info\nexit\n' > "$TMP"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs" --script "$TMP"
rm -f "$TMP"
