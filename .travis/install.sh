#!/bin/bash
set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    curl -O https://bootstrap.pypa.io/get-pip.py
    python get-pip.py --user
    python -m pip install --user virtualenv
    python -m virtualenv ~/.venv
    source ~/.venv/bin/activate

    if [[ "${TOXENV}" == "py35-alldeps-withcov-macos,codecov-publish" ]]; then

        brew upgrade;
        brew install pyenv;
        pyenv install -s 3.5.2;
        pyenv global system 3.5.2;
    fi
fi

# Temporary workaround for https://github.com/pypa/setuptools/issues/776;
# install (and thereby cache a built wheel of) cryptography.  (NB: We're
# already using the same Python version in this venv as in the test env,
# thanks to travis.yml).
pip install -U pip 'setuptools<26'
pip install cryptography

pip install $@
