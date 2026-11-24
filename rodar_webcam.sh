#!/usr/bin/env bash
cd "$(dirname "$0")"
if command -v python3 &>/dev/null; then
    python3 rodar.py 0 "$@"
elif command -v python &>/dev/null; then
    python rodar.py 0 "$@"
else
    echo "Python não foi encontrado no sistema. Por favor instale o Python 3."
    exit 1
fi
