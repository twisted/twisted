#!/usr/bin/env sh
#
# Helper for running twistedchecker and reporting only errors that are part
# of the changes since trunk.
#
# Call it as:
# * SCRIPT_NAME twisted
# * SCRIPT_NAME twisted/words/
# * SCRIPT_NAME twisted.words

target=$1

# FIXME: https://github.com/twisted/twistedchecker/issues/116
# Since for unknown modules twistedchecker will return the same error, the
# diff will fail to detect that we are trying to check an invalid path or
# module.
# This is why we check that the argument is a path and if not a path, it is
# an importable module.
if [ ! -d "$target" ]; then
    python -c "import $target" 2> /dev/null
    if [ $? -ne 0 ]; then
        >&2 echo "$target does not exists as a path or as a module."
        exit 1
    fi
fi

mkdir -p build/trunk-checkout
cd build/trunk-checkout
git --work-tree . checkout origin/trunk .
twistedchecker $target > baseline.result
cd ../..
twistedchecker --diff=build/trunk-checkout/baseline.result $target
exit $?
