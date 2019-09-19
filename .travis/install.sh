#!/bin/bash
#
# Helper for setting up the test environment on Travis.
#
# High level variables action as configuration should be defined in .travis.yml
#
# If running the tests requires a virtualenv, it creates it at `~/.venv` as the
# test run step will activate the virtualenv from that location.
#
set -e
set -x

# We need to test on machines that do not have IPv6, because this is a
# supported configuration and we've broken our tests for this in the past.
# See https://twistedmatrix.com/trac/ticket/9144
if [[ "${DISABLE_IPV6}" = "yes" ]]; then
    sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1
    sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1
fi

#
# Create a virtualenv if required.
#
if [[ "$TRAVIS_PYTHON_VERSION" =~ "pypy*" ]]; then
    if [ -f "$PYENV_ROOT/bin/pyenv" ]; then
        # pyenv already exists. Just updated it.
        (
            cd "$PYENV_ROOT";
            git pull;
        );
    else
        rm -rf "$PYENV_ROOT";
        git clone --depth 1 https://github.com/yyuu/pyenv.git "$PYENV_ROOT";
    fi;

    "$PYENV_ROOT/bin/pyenv" install --skip-existing "$PYPY_VERSION";
    virtualenv --python="$PYENV_ROOT/versions/$PYPY_VERSION/bin/python" ~/.venv;
fi;

#
# Activate the virtualenv if required.
#
if [ -f ~/.venv/bin/activate ]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate
fi;

# Temporary workaround for https://github.com/pypa/setuptools/issues/776;
# install (and thereby cache a built wheel of) cryptography.  (NB: We're
# already using the same Python version in this venv as in the test env,
# thanks to travis.yml).
pip install -U pip 'setuptools<26'
pip install cryptography

# 'pip install cryptography' is already using the same Python version in this
# venv as in the test env, thanks to travis.yml.

#
# Do the actual install work.
#
pip install $@
