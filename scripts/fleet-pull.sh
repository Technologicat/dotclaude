#!/usr/bin/env bash
#
# Pull the whole project fleet from GitHub: clone what is missing, fast-forward
# what is present.
#
#     fleet-pull.sh [-n|--dry-run] [project ...]
#
# With no project names, acts on the whole fleet. Names are local directory
# names (`raven`, `wlsqm`), not GitHub repository names.
#
# Written for the switch between dev machines: you pushed on one, you sit down
# at the other. So the design leans hard on "never surprise the user" — every
# case that needs a human decision stops and says so, rather than guessing.
#
# Five decisions worth knowing about:
#
#   - The project table below is the list of clone URLs, but ~/.claude/CLAUDE.md
#     is the authoritative list of *projects*. These can drift, so the script
#     cross-checks them at startup and warns in both directions. The table has
#     to exist separately because the GitHub repository name is not derivable
#     from the local directory name: ~/Documents/koodit/wlsqm is the repository
#     Technologicat/python-wlsqm.
#
#   - Fetch first, then decide. A repo with nothing to pull is left completely
#     alone — no stash, no merge, no touching the working tree. Most runs will
#     find most of the fleet already current, and the safest handling of a
#     no-op is to do nothing at all.
#
#   - Fast-forward only. If a repo is both ahead and behind, that is unpushed
#     work meeting new upstream work, and resolving it is a decision (merge?
#     rebase? which first?) that belongs to you, not to a sync script. Alert
#     and skip. "Ahead only" is reported too — it is free to compute and it is
#     exactly the thing you want to know when you sit down at the other machine.
#
#   - Stash covers tracked changes only, never `-u`. Untracked files in these
#     repos are deliberate scratch (todo.org, coverage output, tarballs); a run
#     that swept them into a stash stack every time would be worse than useless.
#     The case this gives up on is narrow — an incoming commit adds a path that
#     exists locally as an untracked file — and git handles it well: the merge
#     aborts before touching anything, and that surfaces as an alert.
#
#   - The fleet includes the repo this script lives in, so a run can pull a new
#     version of the script while it is executing. Measured rather than assumed:
#     git checkout writes a *new* file and moves it into place instead of editing
#     the existing one, so the inode changes and the running shell keeps reading
#     the one it opened. The run therefore finishes coherently as the version it
#     started as, and a pulled change takes effect on the next run. (Bash reads a
#     script incrementally rather than slurping it, which is why this needed
#     checking at all; a genuinely in-place rewrite would be a real hazard.)
#
# Anything that needs your attention is reported in the summary and sets the
# exit status to 1.

FLEET_ROOT="$HOME/Documents/koodit"
GITHUB_USER="Technologicat"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"

# Project name, the GitHub repository it clones from, and — only for a project
# that does not live in the fleet root — where it lives on disk instead.
PROJECTS=(
    "dotclaude              dotclaude              $HOME/.claude"

    "pylu                   pylu"
    "pydgq                  pydgq"
    "wlsqm                  python-wlsqm"
    "pyan                   pyan"
    "mcpyrate               mcpyrate"
    "unpythonic             unpythonic"
    "raven                  raven"
    "chandra                chandra"
    "arxiv-api-search       arxiv-api-search"
    "substrate-independent  substrate-independent"
)

if [ -t 1 ]; then
    C_RESET=$'\e[0m'
    C_BOLD=$'\e[1m'
    C_RED=$'\e[31m'
    C_GREEN=$'\e[32m'
    C_YELLOW=$'\e[33m'
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""
fi

DRY_RUN=false
SELECTED=()
RESULTS=()          # "LEVEL|project|message" — messages must not contain '|'

usage() {
    echo "usage: fleet-pull.sh [-n|--dry-run] [project ...]"
}

# Record the outcome of one project, for the summary at the end.
# Levels: OK (nothing to do), CHANGED (pulled or cloned), SKIP (deliberately
# left alone), ALERT (needs a human).
record() {
    RESULTS+=("$1|$2|$3")
}

project_dirs() {
    printf '%s\n' "${PROJECTS[@]}" | awk '{print $1}'
}

# Where each project lives, written the way CLAUDE.md writes paths, so the two
# can be compared directly.
project_paths() {
    local entry dir repo path
    for entry in "${PROJECTS[@]}"; do
        read -r dir repo path <<<"$entry"
        [ -n "$path" ] || path="$FLEET_ROOT/$dir"
        echo "${path/#$HOME/\~}"
    done
}

# Warn if the table above and the project list in CLAUDE.md have drifted apart.
# CLAUDE.md lists each project's path in backticks, which is specific enough to
# pick out exactly the fleet: the bare fleet root and paths to files inside a
# project both fail to match.
check_project_list() {
    if [ ! -r "$CLAUDE_MD" ]; then
        printf '%swarning:%s cannot read %s, skipping project-list cross-check\n' \
               "$C_YELLOW" "$C_RESET" "$CLAUDE_MD"
        return
    fi

    local listed tabled only_listed only_tabled path
    # The backticks below are literal text to match in CLAUDE.md, not a substitution.
    # shellcheck disable=SC2016
    listed=$(grep -oE '`(~/Documents/koodit/[A-Za-z0-9_.-]+|~/\.claude)`' "$CLAUDE_MD" |
                 tr -d '`' | sort -u)
    tabled=$(project_paths | sort -u)

    only_listed=$(comm -23 <(echo "$listed") <(echo "$tabled"))
    only_tabled=$(comm -13 <(echo "$listed") <(echo "$tabled"))

    for path in $only_listed; do
        printf '%swarning:%s %s is in CLAUDE.md but not in this script — add it, with its GitHub repository name\n' \
               "$C_YELLOW" "$C_RESET" "$path"
    done
    for path in $only_tabled; do
        printf '%swarning:%s %s is in this script but no longer in CLAUDE.md — retired?\n' \
               "$C_YELLOW" "$C_RESET" "$path"
    done
}

is_selected() {
    [ ${#SELECTED[@]} -eq 0 ] && return 0
    local name
    for name in "${SELECTED[@]}"; do
        [ "$name" = "$1" ] && return 0
    done
    return 1
}

sync_project() {
    local dir="$1" repo="$2" path="$3"
    local url="git@github.com:$GITHUB_USER/$repo.git"

    printf '\n%s==> %s%s\n' "$C_BOLD" "$dir" "$C_RESET"

    if [ ! -e "$path" ]; then
        if $DRY_RUN; then
            record SKIP "$dir" "missing; would clone from $url"
            return
        fi
        mkdir -p "$(dirname "$path")"
        if git clone "$url" "$path"; then
            record CHANGED "$dir" "cloned"
        else
            record ALERT "$dir" "clone failed"
        fi
        return
    fi

    if [ ! -d "$path/.git" ]; then
        record ALERT "$dir" "exists but is not a git repository; left alone"
        return
    fi

    local branch upstream
    branch=$(git -C "$path" symbolic-ref --quiet --short HEAD)
    if [ -z "$branch" ]; then
        record ALERT "$dir" "detached HEAD; skipped"
        return
    fi
    upstream=$(git -C "$path" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)
    if [ -z "$upstream" ]; then
        record ALERT "$dir" "branch '$branch' has no upstream; skipped"
        return
    fi

    echo "    on $branch, tracking $upstream"
    if ! git -C "$path" fetch --prune --quiet; then
        record ALERT "$dir" "fetch failed (network? ssh agent?); skipped"
        return
    fi

    local counts ahead behind
    if ! counts=$(git -C "$path" rev-list --left-right --count "HEAD...$upstream"); then
        record ALERT "$dir" "cannot compare $branch with $upstream; skipped"
        return
    fi
    read -r ahead behind <<<"$counts"

    if [ "$behind" -eq 0 ]; then
        if [ "$ahead" -gt 0 ]; then
            record SKIP "$dir" "up to date, but $ahead local commit(s) not pushed"
        else
            record OK "$dir" "up to date"
        fi
        return
    fi
    if [ "$ahead" -gt 0 ]; then
        record ALERT "$dir" "diverged: $ahead local commit(s) vs $behind upstream; resolve by hand"
        return
    fi

    local dirty=false
    git -C "$path" diff --quiet HEAD || dirty=true

    if $DRY_RUN; then
        if $dirty; then
            record SKIP "$dir" "would stash local changes, fast-forward $behind commit(s), then pop"
        else
            record SKIP "$dir" "would fast-forward $behind commit(s)"
        fi
        return
    fi

    local stashed=false
    if $dirty; then
        echo "    stashing local changes"
        if git -C "$path" stash push --quiet --message "fleet-pull.sh: before fast-forward"; then
            stashed=true
        else
            record ALERT "$dir" "git stash failed; skipped, nothing changed"
            return
        fi
    fi

    if ! git -C "$path" merge --ff-only "$upstream"; then
        local msg="fast-forward failed (untracked file in the way?); repo unchanged"
        if $stashed; then
            # Never leave the changes stranded in a stash the user was not told about.
            if git -C "$path" stash pop --index; then
                msg="$msg, local changes restored"
            else
                msg="$msg, and the stash will not reapply either; see 'git -C $path stash list'"
            fi
        fi
        record ALERT "$dir" "$msg"
        return
    fi

    local head
    head=$(git -C "$path" log -1 --format='%h %s')
    if ! $stashed; then
        record CHANGED "$dir" "fast-forwarded $behind commit(s), now at $head"
        return
    fi

    # A conflicting pop keeps the stash entry, so nothing is lost — the working
    # tree has the conflict markers and the stash is still on the stack.
    if git -C "$path" stash pop --index; then
        record CHANGED "$dir" "fast-forwarded $behind commit(s), local changes reapplied, now at $head"
    else
        record ALERT "$dir" "fast-forwarded $behind commit(s), but local changes conflict; resolve in $path, then 'git stash drop'"
    fi
}

print_summary() {
    local entry level name msg color alerts=0

    printf '\n%s── summary ──%s\n' "$C_BOLD" "$C_RESET"
    for entry in "${RESULTS[@]}"; do
        IFS='|' read -r level name msg <<<"$entry"
        case "$level" in
            OK)      color="$C_GREEN"  ;;
            CHANGED) color="$C_GREEN"  ;;
            SKIP)    color="$C_YELLOW" ;;
            ALERT)   color="$C_RED"; alerts=$((alerts + 1)) ;;
        esac
        printf '  %s%-7s%s %-22s %s\n' "$color" "$level" "$C_RESET" "$name" "$msg"
    done

    if [ "$alerts" -gt 0 ]; then
        printf '\n%s%d project(s) need your attention.%s\n' "$C_RED" "$alerts" "$C_RESET"
        return 1
    fi
    return 0
}

for arg in "$@"; do
    case "$arg" in
        -n|--dry-run) DRY_RUN=true ;;
        -h|--help)    usage; exit 0 ;;
        -*)           echo "fleet-pull.sh: unknown option: $arg" >&2; usage >&2; exit 2 ;;
        *)            SELECTED+=("$arg") ;;
    esac
done

# Catch a typo in a project name before doing any network work — otherwise the
# script would silently act on nothing and report success.
for name in ${SELECTED[@]+"${SELECTED[@]}"}; do
    if ! project_dirs | grep -qx "$name"; then
        echo "fleet-pull.sh: unknown project: $name" >&2
        echo "known projects: $(project_dirs | tr '\n' ' ')" >&2
        exit 2
    fi
done

check_project_list

$DRY_RUN && printf '%sdry run: nothing will be changed%s\n' "$C_BOLD" "$C_RESET"

for entry in "${PROJECTS[@]}"; do
    read -r dir repo path <<<"$entry"
    [ -n "$path" ] || path="$FLEET_ROOT/$dir"
    is_selected "$dir" && sync_project "$dir" "$repo" "$path"
done

print_summary
