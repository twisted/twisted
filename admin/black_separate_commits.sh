#!/bin/bash
# This is a helper for creating a separate commit for every file that was
# automatically updated by black.
#
# This is designed to be used after black was updated and it needs to
# change many files at once.
#
# To use this script:
# * Update the black version in .pre-commit-config.yaml
# * Commit the .pre-commit-config.yaml change
# * Run `pre-commit run --all`
# * Run this script.
#
for file in $(git diff --name-only)
do
    git commit -m "Black auto-update: $file." $file
done
