"""
Helper to build and install the extensions while running from tox created
virtualenvs.
"""
import os
import sys

# Extensions source files are not installed, so we need to go to root repo dir.
os.chdir(sys.argv[1])
# Have root repo dir in sys.path so that we can import setup.py.
sys.path.insert(0, os.path.abspath(sys.argv[1]))

# While setup.main takes an argument, we still need to set the global sys.argv.
sys.argv = ['setup.py', 'build_ext', '-i']
import setup
setup.main(sys.argv[1:])
