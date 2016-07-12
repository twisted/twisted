#!/bin/bash
#
# Copied from
# https://github.com/pyca/cryptography/blob/master/.travis/install.sh
#

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update

    brew outdated openssl || brew upgrade openssl

    # install pyenv
    git clone https://github.com/yyuu/pyenv.git ~/.pyenv
    PYENV_ROOT="$HOME/.pyenv"
    PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"

    case "${TOXENV}" in
        py27)
            curl -O https://bootstrap.pypa.io/get-pip.py
            python get-pip.py --user
            ;;
        py33)
            pyenv install 3.3.6
            pyenv global 3.3.6
            ;;
        py34)
            pyenv install 3.4.4
            pyenv global 3.4.4
            ;;
        py35)
            pyenv install 3.5.1
            pyenv global 3.5.1
            ;;
        pypy*)
            pyenv install "pypy-$PYPY_VERSION"
            pyenv global "pypy-$PYPY_VERSION"
            ;;
        pypy3)
            pyenv install pypy3-2.4.0
            pyenv global pypy3-2.4.0
            ;;
        docs)
            curl -O https://bootstrap.pypa.io/get-pip.py
            python get-pip.py --user
            ;;
    esac
    pyenv rehash
    python -m pip install --user virtualenv
else
    # temporary pyenv installation to get latest pypy until the travis
    # container infra is upgraded
    if [[ "${TOXENV}" = pypy* ]]; then
        git clone https://github.com/yyuu/pyenv.git ~/.pyenv
        PYENV_ROOT="$HOME/.pyenv"
        PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
        pyenv install "pypy-$PYPY_VERSION"
        pyenv global "pypy-$PYPY_VERSION"
    fi

    pip install virtualenv
fi

python -m virtualenv ~/.venv
source ~/.venv/bin/activate
pip install $@
