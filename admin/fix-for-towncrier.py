#!/usr/bin/env python

"""
Twisted moved the C{twisted} hierarchy to the C{src} hierarchy, but C{git}
doesn't know how to track moves of directories, only files.  Therefore any
files added in branches after this move will be added into ./twisted/ and need
to be moved over into
"""

import os

from twisted.python.filepath import FilePath

here = FilePath(__file__).parent().parent()
twistedPath = here.child("src").child("twisted")


def mv(fromPath):
    for fn in fromPath.walk():
        if fn.isfile():
            os.system(
                "git mv {fr} {to}".format(
                    fr=fn.path,
                    to=fn.parent()
                    .parent()
                    .child("newsfragments")
                    .child(fn.basename())
                    .path,
                )
            )


if twistedPath.child("topfiles").exists():
    mv(twistedPath.child("topfiles"))

for child in twistedPath.listdir():
    path = twistedPath.child(child).child("topfiles")
    if path.exists():
        mv(path)
