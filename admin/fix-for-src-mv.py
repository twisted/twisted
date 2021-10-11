#!/usr/bin/env python

"""
Twisted moved the C{twisted} hierarchy to the C{src} hierarchy, but C{git}
doesn't know how to track moves of directories, only files.  Therefore any
files added in branches after this move will be added into ./twisted/ and need
to be moved over into.
"""

import os

from twisted.python.filepath import FilePath

here = FilePath(__file__).parent().parent()
fromPath = here.child("twisted")
toPath = here.child("src")

for fn in fromPath.walk():
    if fn.isfile():
        os.system("git mv {it} src/{it}".format(it="/".join(fn.segmentsFrom(here))))

os.system("git clean -fd")
