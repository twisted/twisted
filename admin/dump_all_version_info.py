import importlib.metadata
import os
import sys

print("::group::Python info")
print(sys.prefix)
print(sys.exec_prefix)
print(sys.executable)
print(sys.version)
print(sys.platform)
print("::endgroup::")

_entry_points = importlib.metadata.entry_points

if os.environ.get("CI", "").lower() == "true":
    # On CI show the exact deps found at runtime.
    # Skipped on local dev to speed up the test execution.
    print("::group::Deps info")
    for ep in _entry_points(group="console_scripts", name="pip"):
        ep.load()(["freeze", "--all"])
        break
    print("::endgroup::")
