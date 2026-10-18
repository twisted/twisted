"""Script used by test_process.TestTwoProcesses"""

# run until stdin is closed, then quit

import sys

print("ready", flush=True)

while 1:
    d = sys.stdin.read()
    if len(d) == 0:
        sys.exit(0)
