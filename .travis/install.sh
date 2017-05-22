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

        brew update;
        brew upgrade openssl;
        brew install pyenv;
        PYENV_ROOT="$HOME/.pyenv";
        PATH="$PYENV_ROOT/bin:$PATH";
        eval "$(pyenv init -)";
        pyenv install -s 3.5.2;
        pyenv global system 3.5.2;
        pyenv rehash;

    fi
fi

# We need to test on machines that do not have IPv6, because this is a
# supported configuration and we've broken our tests for this in the past.
# See https://twistedmatrix.com/trac/ticket/9144
if [[ "${DISABLE_IPV6}" = "yes" ]]; then
    sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
    sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
fi

# Temporary workaround for https://github.com/pypa/setuptools/issues/776;
# install (and thereby cache a built wheel of) cryptography.  (NB: We're
# already using the same Python version in this venv as in the test env,
# thanks to travis.yml).
pip install -U pip 'setuptools<26'
pip install cryptography

pip install $@
