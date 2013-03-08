# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This makes sure Twisted-using child processes used in the test suite import
# the correct version of Twisted (ie, the version of Twisted under test).

# This is a copy of the bin/_preamble.py script because it's not clear how to
# use the functionality for both things without having a copy.

import sys, os

path = os.path.abspath(sys.argv[0])
while os.path.dirname(path) != path:
    if os.path.exists(os.path.join(path, 'twisted', '__init__.py')):
        sys.path.insert(0, path)
        break
    path = os.path.dirname(path)
