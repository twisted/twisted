# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.service}.
"""

from __future__ import absolute_import, division

from zope.interface import implementer
from zope.interface.exceptions import BrokenImplementation
from zope.interface.verify import verifyObject

from twisted.persisted.sob import IPersistable
from twisted.application.service import Application, IProcess
from twisted.application.service import IService, IServiceCollection
from twisted.application.service import Service
from twisted.python.compat import _PY3
from twisted.trial.unittest import TestCase


@implementer(IService)
class AlmostService(object):
    """
    Almost implement IService.

    Implement IService except for the
    attributes.
    """
    def setName(self, name):
        """
        Do nothing.

        @param name: ignored
        """
        pass


    def setServiceParent(self, parent):
        """
        Do nothing.

        @param parent: ignored
        """
        pass


    def disownServiceParent(self):
        """
        Do nothing.
        """
        pass


    def privilegedStartService(self):
        """
        Do nothing.
        """
        pass


    def startService(self):
        """
        Do nothing.
        """
        pass


    def stopService(self):
        """
        Do nothing.
        """
        pass



class ServiceInterfaceTests(TestCase):
    """
    Tests for IService implementation.
    """
    def setUp(self):
        """
        Build something that implements IService.
        """
        self.almostService = AlmostService()
        self.almostService.parent = None
        self.almostService.running = False
        self.almostService.name = None


    def test_realService(self):
        """
        Service implements IService.
        """
        myService = Service()
        verifyObject(IService, myService)


    def test_hasAll(self):
        """
        AlmostService implements IService.
        """
        verifyObject(IService, self.almostService)


    def test_noName(self):
        """
        AlmostService with no name does not implement IService.
        """
        del self.almostService.name
        with self.assertRaises(BrokenImplementation):
            verifyObject(IService, self.almostService)


    def test_noParent(self):
        """
        AlmostService with no parent does not implement IService.
        """
        del self.almostService.parent
        with self.assertRaises(BrokenImplementation):
            verifyObject(IService, self.almostService)


    def test_noRunning(self):
        """
        AlmostService with no running does not implement IService.
        """
        del self.almostService.running
        with self.assertRaises(BrokenImplementation):
            verifyObject(IService, self.almostService)



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
        self.assertTrue(verifyObject(IPersistable, IPersistable(app)))
