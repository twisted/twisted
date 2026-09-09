"""Write to a file descriptor and then close it, waiting for EOF on stdin before
quitting. This serves to make sure SIGCHLD is actually being noticed.
"""

import os
import sys

print("here is some text")
print("goodbye")
sys.stdout.flush()

os.close(1)
os.close(2)

# Remain alive until the parent has observed stdout closing.
sys.stdin.buffer.read()
