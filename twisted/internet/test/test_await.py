# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A wrapper for L{twisted.internet.test._awaittests}, as that test module
includes keywords not valid in Pythons before 3.5.
"""

try:
    from twisted.python.compat import execfile
    from twisted.python.filepath import FilePath

    _path = FilePath(__file__).parent().child("_awaittests.py.3only")

    _g = {}
    execfile(_path.path, _g)

    AwaitTests = _g["AwaitTests"]
    __all__ = ["AwaitTests"]
except:
    __all__ = []
