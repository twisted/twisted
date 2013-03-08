
"""Write to a handful of file descriptors, to test the childFDs= argument of
reactor.spawnProcess()
"""

import os, sys

debug = 0

if debug: stderr = os.fdopen(2, "w")

if debug: print >>stderr, "this is stderr"

abcd = os.read(0, 4)
if debug: print >>stderr, "read(0):", abcd
if abcd != "abcd":
    sys.exit(1)

if debug: print >>stderr, "os.write(1, righto)"

os.write(1, "righto")

efgh = os.read(3, 4)
if debug: print >>stderr, "read(3):", efgh
if efgh != "efgh":
    sys.exit(2)

if debug: print >>stderr, "os.close(4)"
os.close(4)

eof = os.read(5, 4)
if debug: print >>stderr, "read(5):", eof
if eof != "":
    sys.exit(3)

if debug: print >>stderr, "os.write(1, closed)"
os.write(1, "closed")

if debug: print >>stderr, "sys.exit(0)"
sys.exit(0)
