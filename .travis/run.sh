#!/bin/bash
set -e
set -x

if [[ "$(uname -s)" == "Darwin" ]]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate

    if [[ "${TOXENV}" == "py35-alldeps-withcov-macos,codecov-publish" ]]; then
        # Add pyenv path
        PYENV_ROOT="$HOME/.pyenv";
        PATH="$PYENV_ROOT/bin:$PATH";
        eval "$(pyenv init -)";
    fi
fi

tox -- $TOX_FLAGS
