#!/usr/bin/env bash
# Оба параметра: полный стартовый скрипт на deep.b64
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/src/main.py" --vfs "$ROOT/src/vfs/deep.b64" --script "$ROOT/src/start"
