"""Test program for processes."""

import sys

# stage 1
sys.stdin.read(4)

# stage 2
sys.stdout.write("abcd")
sys.stdout.flush()
sys.stdout.close()

# stage 3
sys.stderr.write("1234")
sys.stderr.flush()
sys.stderr.close()

# stage 4
sys.stdin.read(4)
