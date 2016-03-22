# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import absolute_import, division

import os

from functools import wraps

from twisted.python.compat import _PY3

if _PY3 or int(os.environ.get('TWISTED_NEWSTYLE', 0)) == 0:

    def _oldStyle(cls):
        return cls

else:

    def _oldStyle(cls):

        class OverwrittenClass(cls, object):
            pass

        OverwrittenClass.__name__ = cls.__name__
        OverwrittenClass.__module__ = cls.__module__

        return OverwrittenClass
