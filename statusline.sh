#!/bin/bash
# Claude Code status line: PS1-style prompt + model + thinking effort + context usage
input=$(cat)
pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | xargs printf '%.0f')
model=$(echo "$input" | jq -r '.model.display_name // "unknown model"')
effort=$(jq -r '.effortLevel // "normal"' "$HOME/.claude/settings.json" 2>/dev/null || echo "normal")
venv_prefix=""
if [ -n "$VIRTUAL_ENV" ]; then
    venv_name=$(sed -n 's/^prompt *= *//p' "$VIRTUAL_ENV/pyvenv.cfg" 2>/dev/null)
    venv_prefix="(${venv_name:-$(basename "$VIRTUAL_ENV")}) "
fi
printf '%s\033[01;32m%s@%s\033[00m:\033[01;34m%s\033[00m  \033[00;36m%s\033[00m  effort \033[00;33m%s\033[00m  ctx %s%%' \
    "$venv_prefix" "$(whoami)" "$(hostname -s)" "$(pwd)" "$model" "$effort" "$pct"
