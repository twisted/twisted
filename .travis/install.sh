#!/bin/bash
set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    curl -O https://bootstrap.pypa.io/get-pip.py
    python get-pip.py --user
    python -m pip install --user virtualenv
    python -m virtualenv ~/.venv

    # Temporary workaround for https://github.com/pypa/setuptools/issues/776;
    # install (and thereby cache a built wheel of) cryptography.  (NB: We're
    # already using the same Python version in this venv as in the test env,
    # thanks to travis.yml).
    python -m pip install 'setuptools<26'
    python -m pip install cryptography

    source ~/.venv/bin/activate
fi

pip install $@
