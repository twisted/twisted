# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Tests for L{twisted.application.service}.
"""

from zope.interface.verify import verifyObject

from twisted.application.service import (
    Application,
    IProcess,
    IService,
    IServiceCollection,
    )
from twisted.python.compat import _PY3
from twisted.trial.unittest import TestCase



class ApplicationTests(TestCase):
    """
    Tests for L{twisted.application.service.Application} function.
    """

    def test_ApplicationComponents(self):
        """
        Check L{twisted.application.service.Application} instantiation.
        """
        sut = Application('app-name')

        self.assertTrue(verifyObject(IService, IService(sut)))
        self.assertTrue(
            verifyObject(IServiceCollection, IServiceCollection(sut)))
        self.assertTrue(verifyObject(IProcess, IProcess(sut)))

        if not _PY3:
           # TODO https://twistedmatrix.com/trac/ticket/6910
           # twisted.persisted is proposed for deprecation and is not yet
           # ported to to Python3.
            from twisted.persisted.sob import IPersistable
            self.assertTrue(verifyObject(IPersistable, IPersistable(sut)))
