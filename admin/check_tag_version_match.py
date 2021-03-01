#
# Used during the release process to make sure that we release based on a
# tag that has the same version as the current twisted.__version.
#
# Designed to be conditionally called inside GitHub Actions release job.
# Tags should use PEP440 version scheme.
#
# To be called as: admin/check_tag_version_match.py refs/tags/twisted-20.3.0
#
import sys

import pep517.meta

TAG_PREFIX = "refs/tags/twisted-"

if len(sys.argv) < 2:
    print("No tag check requested.")
    sys.exit(0)

branch_version = pep517.meta.load(".").version
run_version = sys.argv[1]

if not run_version.startswith(TAG_PREFIX):
    print(f"Not a twisted release tag name '{run_version}.")
    sys.exit(1)

run_version = run_version[len(TAG_PREFIX) :]

if run_version != branch_version:
    print(f"Branch is at '{branch_version}' while tag is '{run_version}'")
    exit(1)

print(f"All good. Branch and tag versions match for '{branch_version}'.")
sys.exit(0)
