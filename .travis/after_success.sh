#!/bin/bash
set -e
set -x

if [ -f ~/.venv/bin/activate ]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate
fi

JOB_URL="https://travis-ci.org/twisted/twisted/jobs/$TRAVIS_JOB_NUMBER"
python admin/ci_github_commit_status.py \
    --commit=$TRAVIS_COMMIT \
    --state='success' \
    --target-url=$JOB_URL \
    --description='Job done' \
    --context="continuous-integration/travis-ci/job/$TOXENV"