# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A wrapper for L{twisted.internet.test._awaittests}, as that test module
includes keywords not valid in Pythons before 3.5.
"""

try:
    from twisted.internet.test._awaittests import AwaitTests
    __all__ = ["AwaitTests"]
except:
    pass
