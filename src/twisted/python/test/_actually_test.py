# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A module that uses L{_actually}
"""
from twisted.python._pydoctor import _actually


def theFunction():
    """
    A function that L{_actually} will alias.
    """



@_actually(theFunction)
def theAlias():
    """
    The alias for L{theFunction}.
    """
