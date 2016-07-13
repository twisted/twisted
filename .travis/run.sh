#!/bin/bash
set -e
set -x

if [[ "$(uname -s)" == "Darwin" ]]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate
fi

tox -- $TOX_FLAGS
