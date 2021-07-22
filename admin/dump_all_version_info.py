import os
import sys
import pkg_resources

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
    for ep in pkg_resources.iter_entry_points(group="console_scripts", name="pip"):
        ep.load()(["freeze", "--all"])
        break
    print("::endgroup::")
