# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import absolute_import, division

import os
import types
import inspect

from twisted.python.reflect import namedAny, fullyQualifiedName
from twisted.python.modules import getModule
from twisted.python.compat import _PY3
from twisted.trial import unittest

skip = None

if _PY3:
    skip = "Not relevant on Python 3."
elif not int(os.environ.get('TWISTED_NEWSTYLE', 0)) == 1:
    skip = "Not running with TWISTED_NEWSTYLE=1"


if not skip:

    class NewStyleOnly(object):
        """
        A testclass that takes a module and tests if the classes defined in it
        are old-style.

        CAVEATS: This is maybe slightly dumb, and only looks in non-test
        modules (because some test modules have side effects). It also doesn't
        look inside functions, for classes defined there, or nested classes.
        """
        module = None

        def test_newStyleClassesOnly(self):
            try:
                module = namedAny(self.module)
            except ImportError:
                raise unittest.SkipTest("Not importable.")

            for name, val in inspect.getmembers(module):
                if hasattr(val, "__module__") \
                   and val.__module__ == self.module:
                    if isinstance(val, types.ClassType):
                        raise unittest.FailTest(
                            "{val} is an old-style class".format(
                                val=fullyQualifiedName(val)))

    for x in getModule("twisted").walkModules():
        if ".test." in x.name:
            continue

        class test(NewStyleOnly, unittest.TestCase):
            module = x.name

        acceptableName = x.name.replace(".", "_")
        test.__name__ = acceptableName
        locals().update({acceptableName: test})

else:

    class NewStyleOnly(unittest.TestCase):
        """
        Just skip, it doesn't make sense right now.
        """
        def test_newStyleClassesOnly(self):
            raise unittest.SkipTest(skip)
