#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.words.protocols import msn
from twisted.python import log

# System Imports
import sys, getpass

"""
This example connects to the MSN chat service and
prints out information about all the users on your
contact list (both online and offline).

The main aim of this example is to demonstrate
the connection process.

@author Samuel Jordan
"""


def _createNotificationFac():
    fac = msn.NotificationFactory()
    fac.userHandle = USER_HANDLE
    fac.password = PASSWORD
    fac.protocol = Notification
    return fac

class Dispatch(msn.DispatchClient):

    def __init__(self):
        msn.DispatchClient.__init__(self)
        self.userHandle = USER_HANDLE

    def gotNotificationReferral(self, host, port):
        self.transport.loseConnection()
        reactor.connectTCP(host, port, _createNotificationFac())

class Notification(msn.NotificationClient):

    def loginFailure(self, message):
        print 'Login failure:', message

    def listSynchronized(self, *args):
        contactList = self.factory.contacts
        print 'Contact list has been synchronized, number of contacts = %s' % len(contactList.getContacts())
        for contact in contactList.getContacts().values():
            print 'Contact: %s' % (contact.screenName,)
            print '    email: %s' % (contact.userHandle,)
            print '   groups:'
            for group in contact.groups:
                print '      - %s' % contactList.groups[group]
            print

if __name__ == '__main__':
    USER_HANDLE = raw_input("Email (passport): ")
    PASSWORD = getpass.getpass()
    log.startLogging(sys.stdout)
    _dummy_fac = ClientFactory()
    _dummy_fac.protocol = Dispatch
    reactor.connectTCP('messenger.hotmail.com', 1863, _dummy_fac)
    reactor.run()
