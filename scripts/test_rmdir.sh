#!/usr/bin/env bash
# Команда rmdir: все режимы и ошибки на VFS rmdir.b64
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/rmdir.b64" \
    --script "$ROOT/src/start_rmdir"
