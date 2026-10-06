#!/usr/bin/env bash
# Без параметров (окно закрыть вручную)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/src/main.py"
