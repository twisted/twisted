
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I contain ResourceUnpickler, which will unpickle any python object
named with the file extension .trp.
"""
import sys, os
from pickle import Unpickler

from twisted.python.components import implements, getAdapter
from twisted.web.resource import IResource

def ResourceUnpickler(path, registry = None):
    fl = open(path)
    result = Unpickler(fl).load()
    return result
