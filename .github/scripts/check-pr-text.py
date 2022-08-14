#
# This script is designed to be called by the GHA workflow.
#
# It is designed to check that the PR text complies to our dev standards.
#
# The input is received via the environmet variables:
# * PR_TITLE - title of the PR
# * PR_BODY - the description of the PR
#
# To test it run
#
# $ export PR_TITLE='#1234 Test Title'
# $ export PR_BODY='some lines
# > Fixes #12345
# > more lines'
# $ python3 .github/scripts/check-pr-text.py
#
import os
import re
import sys

pr_title = os.environ.get("PR_TITLE", "")
pr_body = os.environ.get("PR_BODY", "")

print("--- DEBUG ---")
print(f"Title: {pr_title}")
print(f"Body:\n {pr_body}")
print("-------------")


def fail(message):
    print(message)
    print("Fix the title and then trigger a new push.")
    print("A re-run for this job will not work.")
    sys.exit(1)


if not pr_title:
    fail("Title for the PR not found. " "Maybe missing PR_TITLE env var.")

if not pr_body:
    fail("Body for the PR not found. " "Maybe missing PR_BODY env var.")

title_search = re.search(r"^(#\d+) .+", pr_title)
if not title_search:
    fail(
        "Title of PR has no issue ID reference. It must look like “#1234 Foo bar baz”."
    )
else:
    print(f"PR title is complaint for {title_search[1]}. Good job.")


body_search = re.search(r".*Fixes (#\d+).+", pr_body)
if not body_search:
    fail('Body of PR has no "Fixes #12345" issue ID reference.')
else:
    print(f"PR description is complaint for {body_search[1]}. Good job.")


if title_search[1] != body_search[1]:
    fail("PR title and description have different IDs.")

# All good.
sys.exit(0)
