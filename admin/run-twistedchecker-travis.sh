#!/usr/bin/env sh
#
# Helper for running twistedchecker and reporting only errors that are part
# of the changes since trunk.
#
mkdir .baseline
cd .baseline
git --work-tree . checkout origin/trunk .
twistedchecker vertex > ../.baseline.result
cd ..
twistedchecker --diff=.baseline.result vertex
exit $?
