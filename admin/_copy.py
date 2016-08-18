"""
A cross-platform copying tool that supports globbing.
"""

import sys
import glob
import shutil

for f in glob.glob(sys.argv[1]):
    shutil.copy(f, sys.argv[2])
