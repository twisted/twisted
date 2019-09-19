#!/bin/bash
set -e
set -x

#
# Initialize the virtualenv if one was created at install time.
#
if [ -f ~/.venv/bin/activate ]; then
    source ~/.venv/bin/activate

    if [[ "${TOXENV}" =~ py35-.* ]]; then
        # Add pyenv path
        PYENV_ROOT="$HOME/.pyenv";
        PATH="$PYENV_ROOT/bin:$PATH";
        eval "$(pyenv init -)";
    fi
fi

tox -- $TOX_FLAGS
