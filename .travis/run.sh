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
    source ~/.venv/bin/activate
fi

tox $TOX_FLAGS
