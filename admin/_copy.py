"""
A cross-platform copying tool that supports globbing.
"""

import glob
import shutil
import sys

for f in glob.glob(sys.argv[1]):
    shutil.copy(f, sys.argv[2])
