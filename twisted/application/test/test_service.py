# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Tests for L{twisted.application.service}.
"""

from zope.interface.verify import verifyObject

from twisted.application.service import Application, IProcess
from twisted.application.service import IService, IServiceCollection
from twisted.python.compat import _PY3
from twisted.trial.unittest import TestCase



class ApplicationTests(TestCase):
    """
    Tests for L{twisted.application.service.Application}.
    """
    def test_applicationComponents(self):
        """
        Check L{twisted.application.service.Application} instantiation.
        """
        app = Application('app-name')

        self.assertTrue(verifyObject(IService, IService(app)))
        self.assertTrue(
            verifyObject(IServiceCollection, IServiceCollection(app)))
        self.assertTrue(verifyObject(IProcess, IProcess(app)))


    def test_applicationComponentsArePersistable(self):
        """
        L{twisted.application.service.Application} implements L{IPersistable}.
        """
        app = Application('app-name')

        from twisted.persisted.sob import IPersistable
        self.assertTrue(verifyObject(IPersistable, IPersistable(app)))

    if _PY3:
        # FIXME: https://twistedmatrix.com/trac/ticket/7827
        # twisted.persisted is not yet ported to Python 3
        test_applicationComponentsArePersistable.skip = (
            "twisted.persisted is not yet ported to Python 3.")
