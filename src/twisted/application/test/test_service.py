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
from twisted.trial.unittest import TestCase


@implementer(IService)
class AlmostService(object):
    """
    Implement IService except for the attributes.
    """

    def __init__(self, name, parent, running):
        self.name = name
        self.parent = parent
        self.running = running

    def makeInvalidByDeletingName(self):
        """
        Probably not a wise method to call.
        """
        del self.name

    def makeInvalidByDeletingParent(self):
        """
        Probably not a wise method to call.
        """
        del self.parent

    def makeInvalidByDeletingRunning(self):
        """
        Probably not a wise method to call.
        """
        del self.running

    def setName(self, name):
        """
        See L{twisted.application.service.IService}.

        @param name: ignored
        """


    def setServiceParent(self, parent):
        """
        See L{twisted.application.service.IService}.

        @param parent: ignored
        """


    def disownServiceParent(self):
        """
        See L{twisted.application.service.IService}.
        """


    def privilegedStartService(self):
        """
        See L{twisted.application.service.IService}.
        """


    def startService(self):
        """
        See L{twisted.application.service.IService}.
        """


    def stopService(self):
        """
        See L{twisted.application.service.IService}.
        """



class ServiceInterfaceTests(TestCase):
    """
    Tests for L{twisted.application.service.IService} implementation.
    """
    def setUp(self):
        """
        Build something that implements IService.
        """
        self.almostService = AlmostService(parent=None, running=False,
                                           name=None)


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
        self.almostService.makeInvalidByDeletingName()
        with self.assertRaises(BrokenImplementation):
            verifyObject(IService, self.almostService)


    def test_noParent(self):
        """
        AlmostService with no parent does not implement IService.
        """
        self.almostService.makeInvalidByDeletingParent()
        with self.assertRaises(BrokenImplementation):
            verifyObject(IService, self.almostService)


    def test_noRunning(self):
        """
        AlmostService with no running does not implement IService.
        """
        self.almostService.makeInvalidByDeletingRunning()
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
