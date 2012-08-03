# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This makes sure that users don't have to set up their environment
# specially in order to run trial -j properly.

# This is a copy of the bin/_preamble.py script because it's not clear how to
# use the functionality for both things without having a copy.

import sys, os

path = os.path.abspath(sys.argv[0])
while os.path.dirname(path) != path:
    if os.path.exists(os.path.join(path, 'twisted', '__init__.py')):
        sys.path.insert(0, path)
        break
    path = os.path.dirname(path)

# begin chdir armor
sys.path[:] = map(os.path.abspath, sys.path)
# end chdir armor

sys.path.insert(0, os.path.abspath(os.getcwd()))
