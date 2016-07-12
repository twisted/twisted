#!/bin/bash
#
# Copied from
# https://github.com/pyca/cryptography/blob/master/.travis/run.sh
#
set -e
set -x

if [[ "$(uname -s)" == "Darwin" ]]; then
    # initialize our pyenv
    PYENV_ROOT="$HOME/.pyenv"
    PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
else
    if [[ "${TOXENV}" == "pypy" ]]; then
        PYENV_ROOT="$HOME/.pyenv"
        PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    fi
fi
source ~/.venv/bin/activate
tox -- $TOX_FLAGS
