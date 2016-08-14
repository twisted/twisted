#!/bin/bash
set -e
set -x

if [ -f ~/.venv/bin/activate ]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate
fi

tox -- $TOX_FLAGS
