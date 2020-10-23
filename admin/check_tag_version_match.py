#
# Used during the release process to make sure that we release based on a
# tag that has the same version as the current twisted.__version.
#
# Designed to be conditionally called inside GitHub Actions release job.
#
# To be called as: admin/check_tag_version_match.py refs/tags/twisted-20.3.0
#
import sys
from twisted import __version__

TAG_PREFIX = "refs/tags/twisted-"

if len(sys.argv) < 2:
    print("No tag check requested.")
    sys.exit(0)

run_version = sys.argv[1]

if not run_version.startswith(TAG_PREFIX):
    print("Not a twisted release tag name.")
    sys.exit(1)

run_version = run_version[len(TAG_PREFIX) :]

if run_version != __version__:
    print("Branch is at '{}' while tag is '{}'".format(__version__, run_version))
    exit(1)

print("All good. Branch and tag versions match for "%s"." % (__version__,))
sys.exit(0)
