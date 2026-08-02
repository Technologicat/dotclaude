#!/usr/bin/env bash
#
# Check that fleet-pull.sh does the right thing, against a fixture fleet of
# throwaway repos built from scratch on each run.
#
#     fleet-pull-selftest.sh
#
# Prints one line per assertion and exits nonzero if any failed.
#
# Why a fixture rather than just running the real thing: the interesting paths
# are the ones you cannot summon on demand. A repo that is behind *and* locally
# modified *and* modified in the same place upstream — the stash-pop conflict —
# is exactly what fleet-pull.sh exists to handle gracefully, and exactly what
# you will not have on the morning you want to test it. Here it is one line of
# setup.
#
# This never touches the real fleet: the copy under test is patched so that
# FLEET_ROOT and the clone URL point into the fixture. Nothing else is patched,
# so the project table, the CLAUDE.md cross-check and the dir-to-repository name
# mapping are all exercised as written — the fixture deliberately reuses real
# project names, which is why wlsqm must still clone from `python-wlsqm`.
#
# The fixture lives in /tmp (a ramdisk here, wiped at boot) and is left in place
# after the run, so a failure can be examined where it happened.

set -e

W="${TMPDIR:-/tmp}/fleet-pull-selftest"
rm -rf "$W"
mkdir -p "$W/remotes" "$W/seed" "$W/fleet"

sed -e "s|^FLEET_ROOT=.*|FLEET_ROOT=\"$W/fleet\"|" \
    -e "s|    local url=.*|    local url=\"$W/remotes/\$repo.git\"|" \
    -e "s|\\\$HOME/\\.claude\"|$W/fleet/dotclaude\"|" \
    "$(dirname "$(readlink -f "$0")")/fleet-pull.sh" > "$W/fleet-pull.sh"
chmod +x "$W/fleet-pull.sh"

# dotclaude is the one project reached by an absolute path rather than through
# FLEET_ROOT, so it is also the one the patching above could miss — and missing it
# would point a test run at the real harness repo. Refuse to run if it is still there.
if grep -q 'HOME/\.claude"' "$W/fleet-pull.sh"; then
    echo "selftest: the dotclaude entry was not redirected into the fixture; refusing to run" >&2
    exit 1
fi

# A repository with two files, cloned into the fixture fleet: $1 is the local
# directory name, $2 the name it is published under.
make_repo() {
    local dir="$1" repo="$2"
    git init --bare -q -b master "$W/remotes/$repo.git"
    git init -q -b master "$W/seed/$dir"
    git -C "$W/seed/$dir" config user.email selftest@example.com
    git -C "$W/seed/$dir" config user.name "fleet-pull selftest"
    printf 'a original\n' > "$W/seed/$dir/a.txt"
    printf 'b original\n' > "$W/seed/$dir/b.txt"
    git -C "$W/seed/$dir" add -A
    git -C "$W/seed/$dir" commit -q -m "initial"
    git -C "$W/seed/$dir" remote add origin "$W/remotes/$repo.git"
    git -C "$W/seed/$dir" push -q -u origin master
    git clone -q "$W/remotes/$repo.git" "$W/fleet/$dir"
    git -C "$W/fleet/$dir" config user.email selftest@example.com
    git -C "$W/fleet/$dir" config user.name "fleet-pull selftest"
}

# One commit published upstream, touching a.txt.
upstream_commit() {
    printf 'a UPSTREAM\n' > "$W/seed/$1/a.txt"
    git -C "$W/seed/$1" commit -q -am "upstream edit"
    git -C "$W/seed/$1" push -q origin master
}

make_repo unpythonic unpythonic                 # nothing to do

make_repo pylu pylu                             # clean fast-forward
upstream_commit pylu

make_repo pydgq pydgq                           # dirty, local edit elsewhere in the tree
upstream_commit pydgq
printf 'b LOCAL\n' > "$W/fleet/pydgq/b.txt"

make_repo wlsqm python-wlsqm                    # dirty, local edit collides with the incoming one
upstream_commit wlsqm
printf 'a LOCAL\n' > "$W/fleet/wlsqm/a.txt"

make_repo mcpyrate mcpyrate                     # diverged: unpushed commit meets upstream commit
upstream_commit mcpyrate
printf 'b LOCAL\n' > "$W/fleet/mcpyrate/b.txt"
git -C "$W/fleet/mcpyrate" commit -q -am "local work"

make_repo pyan pyan                             # not on disk at all
rm -rf "$W/fleet/pyan"

make_repo dotclaude dotclaude                   # reached by explicit path, not through FLEET_ROOT
upstream_commit dotclaude

set +e
output=$("$W/fleet-pull.sh" unpythonic pylu pydgq wlsqm mcpyrate pyan dotclaude 2>&1)
status=$?

failures=0

report() {
    if [ "$1" = "pass" ]; then
        printf '  pass  %s\n' "$2"
    else
        printf '  FAIL  %s\n' "$2"
        failures=$((failures + 1))
    fi
}

# $1: extended regex the summary must contain, $2: what it means
expect_summary() {
    if grep -Eq "$1" <<<"$output"; then report pass "$2"; else report fail "$2"; fi
}

# $1: file under the fixture fleet, $2: expected contents, $3: what it means
expect_file() {
    if [ "$(cat "$W/fleet/$1" 2>/dev/null)" = "$2" ]; then
        report pass "$3"
    else
        report fail "$3 (got: $(cat "$W/fleet/$1" 2>/dev/null))"
    fi
}

echo
echo "assertions:"

expect_summary 'OK +unpythonic +up to date'                  "current repo reported up to date"

expect_summary 'CHANGED +pylu +fast-forwarded 1 commit'      "clean repo fast-forwarded"
expect_file    pylu/a.txt "a UPSTREAM"                       "clean repo has the upstream edit"

expect_summary 'CHANGED +pydgq .*local changes reapplied'    "dirty repo stashed, pulled, popped"
expect_file    pydgq/a.txt "a UPSTREAM"                      "dirty repo has the upstream edit"
expect_file    pydgq/b.txt "b LOCAL"                         "dirty repo kept its local edit"

expect_summary 'ALERT +wlsqm .*local changes conflict'       "colliding edit reported as an alert"
if [ "$(git -C "$W/fleet/wlsqm" stash list | wc -l)" -eq 1 ]; then
    report pass "colliding edit is still in the stash"
else
    report fail "colliding edit is still in the stash"
fi
if grep -q '^<<<<<<<' "$W/fleet/wlsqm/a.txt"; then
    report pass "colliding edit left conflict markers to resolve"
else
    report fail "colliding edit left conflict markers to resolve"
fi

expect_summary 'ALERT +mcpyrate +diverged'                   "diverged repo reported as an alert"
expect_file    mcpyrate/b.txt "b LOCAL"                      "diverged repo left untouched"

expect_summary 'CHANGED +dotclaude +fast-forwarded 1 commit' "repo outside the fleet root fast-forwarded"
expect_file    dotclaude/a.txt "a UPSTREAM"                  "repo outside the fleet root has the upstream edit"

expect_summary 'CHANGED +pyan +cloned'                       "missing repo cloned"
if [ -d "$W/fleet/pyan/.git" ]; then
    report pass "cloned repo is a working checkout"
else
    report fail "cloned repo is a working checkout"
fi

if [ "$status" -eq 1 ]; then
    report pass "exit status flags that something needs attention"
else
    report fail "exit status flags that something needs attention (got $status)"
fi

echo
if [ "$failures" -gt 0 ]; then
    printf '%d assertion(s) failed. Fixture kept at %s\n' "$failures" "$W"
    printf 'Output of the run under test:\n%s\n' "$output"
    exit 1
fi
echo "all assertions passed"
