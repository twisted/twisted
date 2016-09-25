#!/bin/bash
set -e
set -x

echo $PATH

tox -- $TOX_FLAGS
