import os
import sys

from pip._internal.cli.main import main

print("::group::Python info")
print(sys.prefix)
print(sys.exec_prefix)
print(sys.executable)
print(sys.version)
print(sys.platform)
print("::endgroup::")

if os.environ.get("CI", "").lower() == "true":
    # On CI show the exact deps found at runtime.
    # Skipped on local dev to speed up the test execution.
    print("::group::Deps info")
    main(["freeze", "--all"])
    print("::endgroup::")
