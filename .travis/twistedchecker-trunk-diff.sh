#!/usr/bin/env sh
#
# Helper for running twistedchecker and reporting only errors that are part
# of the changes since trunk.
#
# Call it as:
# * SCRIPT_NAME twisted
# * SCRIPT_NAME twisted/words/
# * SCRIPT_NAME twisted.words

set -e  # Exit with error is a command exits with an unchecked error.
set -u  # Exit with error if an undefined variable is dereferenced.

target="$1";

# FIXME: https://github.com/twisted/twistedchecker/issues/116
# Since for unknown modules twistedchecker will return the same error, the
# diff will fail to detect that we are trying to check an invalid path or
# module.
# This is why we check that the argument is a path and if not a path, it is
# an importable module.
if [ ! -d "${target}" ]; then
    if ! python -c "import ${target}" 2> /dev/null; then
        >&2 echo "${target} does not exists as a path or as a module.";
        exit 1;
    fi;
fi;

# Make sure we have trunk on the local repo.
git fetch origin "+refs/heads/trunk:refs/remotes/origin/trunk";

# Explicitly ignore extension modules.
# See: https://github.com/twisted/twistedchecker/issues/118
mkdir -p build/;
twistedchecker \
    --ignore="raiser.so,portmap.so,_sendmsg.so" \
    --disable="${TWISTEDCHECKER_SKIP_WARNINGS:-}" \
    --msg-template='{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}' \
    "${target}" \
    > "build/twistedchecker-branch.report" || true;

# Make sure repo is producing the diff with prefix so that the output of
# `git diff` can be parsed by diff_cover.
git config diff.noprefix false;

diff-quality \
    --violations=pylint \
    --fail-under=100 \
    --compare-branch=origin/trunk \
    build/twistedchecker-branch.report;
