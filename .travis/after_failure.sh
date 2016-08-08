#!/bin/bash
set -e
set -x

if [ -f ~/.venv/bin/activate ]; then
    # Initialize the virtualenv created at install time.
    source ~/.venv/bin/activate
fi

JOB_URL="https://travis-ci.org/twisted/twisted/jobs/$TRAVIS_JOB_ID"
python admin/ci_github_commit_status.py \
    --commit=$TRAVIS_COMMIT \
    --state='failure' \
    --target-url=$JOB_URL \
    --description='Job failed.' \
    --context="travis/$TOXENV"
