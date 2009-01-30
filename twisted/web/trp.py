# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
I contain ResourceUnpickler, which will unpickle any python object
named with the file extension .trp.
"""

import warnings
from pickle import Unpickler

_msg = ("is deprecated as of Twisted 9.0.  Resource persistence "
        "is beyond the scope of Twisted Web.")

warnings.warn("twisted.web.trp " + _msg , DeprecationWarning, stacklevel=2)

def ResourceUnpickler(path, registry = None):
    warnings.warn(
        "twisted.web.trp.ResourceUnpickler " + _msg ,
        DeprecationWarning, stacklevel=2)
    fl = open(path)
    result = Unpickler(fl).load()
    return result
