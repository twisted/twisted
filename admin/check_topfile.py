#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Check that the current commits since branching have a topfile.
"""

from __future__ import absolute_import, division, print_function

import os
import sys

from twisted.python._release import runCommand

TOPFILE_TYPES = ["doc", "bugfix", "misc", "feature", "removal"]


def check(location):

    location = os.path.abspath(location)
    r = runCommand([b"git", b"diff", b"--name-only", b"origin/trunk..."],
                   cwd=location)
    files = r.strip().split(os.linesep)

    print("Looking at these files:")
    for change in files:
        print(change)
    print("----")

    for change in files:
        if os.sep + "topfiles" + os.sep in change:
            if change.rsplit(".", 1)[1] in TOPFILE_TYPES:
                print("Found", change)
                sys.exit(0)

    print("No topfile found")
    sys.exit(1)


if __name__ == "__main__":
    check(*sys.argv[1:])
