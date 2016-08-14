#!/bin/bash
set -e
set -x

if [ -f ~/.venv/bin/activate ]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate
fi

# FIXME: https://twistedmatrix.com/trac/ticket/8373
# By default, Travis only clones one branch.
# Some tests require the presence of the `trunk` branch so here we are, also
# fetching `trunk` for each test.
git remote set-branches --add origin trunk
git fetch origin trunk

JOB_URL="https://travis-ci.org/twisted/twisted/jobs/$TRAVIS_JOB_ID"
python admin/ci_github_commit_status.py \
    --commit=$TRAVIS_COMMIT \
    --state='pending' \
    --target-url=$JOB_URL \
    --description='Job in progress.' \
    --context="travis/$TOXENV"
