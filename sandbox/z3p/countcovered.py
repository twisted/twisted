#!/usr/bin/env python
"""
A simple script to count the amount of lines covered by tests.

Example:
bin/trial --coverage -m twisted.test.test_conch
countcovered.py _trial_temp/-m/twisted.conch.*
"""

import sys, os.path
files = sys.argv[1:]
totalLines = 0.0
totalCovered = 0.0
for f in files:
    o = file(f)
    f = os.path.basename(f)
    f = f[:-6]
    lines = 0.0
    covered = 0.0
    for line in o:
        line = line.strip()
        if line:
            start = line.split(':')[0]
            try:
                int(start)
            except ValueError:
                if line.startswith('>'):
                    lines += 1
                continue
            else:
                lines += 1
                covered +=1
    print f, "%i %i %.2f" % (int(covered), int(lines), covered/lines)
    totalLines += lines
    totalCovered += covered
print "TOTAL %i %i %.2f" % (int(totalCovered), int(totalLines), totalCovered/totalLines)
