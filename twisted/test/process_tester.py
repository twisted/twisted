"""Test program for processes."""

import sys, os

# stage 1
sys.stdin.read(4)

# stage 2
sys.stdout.write("abcd")
sys.stdout.flush()
os.close(sys.stdout.fileno())

# and a one, and a two, and a...
sys.stdin.read(4)

# stage 3
sys.stderr.write("1234")
sys.stderr.flush()
sys.stderr.close()
os.close(sys.stderr.fileno())

# stage 4
sys.stdin.read(4)
