#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR/agents"

TARGETS=(
  "$HOME/.agents"
  "$HOME/.claude"
  "$HOME/.cursor"
)

SUBDIRS=(agents commands skills)

for target in "${TARGETS[@]}"; do
  mkdir -p "$target"
  for sub in "${SUBDIRS[@]}"; do
    src="$AGENTS_DIR/$sub"
    dest="$target/$sub"

    [ ! -d "$src" ] && continue

    if [ -L "$dest" ]; then
      existing="$(readlink -f "$dest")"
      if [ "$existing" = "$src" ]; then
        echo "skip $dest (already linked)"
        continue
      fi
      echo "relink $dest -> $src (was $existing)"
      rm "$dest"
    elif [ -d "$dest" ]; then
      echo "backup $dest -> ${dest}.bak"
      mv "$dest" "${dest}.bak"
    fi

    ln -s "$src" "$dest"
    echo "link  $dest -> $src"
  done
done
