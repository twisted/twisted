#!/usr/bin/env sh
#
# Helper for running twistedchecker and reporting only errors that are part
# of the changes since trunk.
#
# Call it as ./admin/twistedchecker-trunk-diff.sh twisted
#
# You can also get errors only for a subset of the files using:
#
# ./admin/twistedchecker-trunk-diff.sh twisted/words
#
target=$1

if [ ! -d "$target" ]; then
    >&2 echo "$target does not exists."
    exit 1
fi

mkdir -p build/trunk-checkout
cd build/trunk-checkout
git --work-tree . checkout origin/trunk .
twistedchecker $target > baseline.result
cd ../..
twistedchecker --diff=build/trunk-checkout/baseline.result $target
exit $?
