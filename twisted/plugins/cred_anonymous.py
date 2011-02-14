# -*- test-case-name: twisted.test.test_strcred -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Cred plugin for anonymous logins.
"""

from zope.interface import implements

from twisted import plugin
from twisted.cred.checkers import AllowAnonymousAccess
from twisted.cred.strcred import ICheckerFactory
from twisted.cred.credentials import IAnonymous


anonymousCheckerFactoryHelp = """
This allows anonymous authentication for servers that support it.
"""


class AnonymousCheckerFactory(object):
    """
    Generates checkers that will authenticate an anonymous request.
    """
    implements(ICheckerFactory, plugin.IPlugin)
    authType = 'anonymous'
    authHelp = anonymousCheckerFactoryHelp
    argStringFormat = 'No argstring required.'
    credentialInterfaces = (IAnonymous,)


    def generateChecker(self, argstring=''):
        return AllowAnonymousAccess()



theAnonymousCheckerFactory = AnonymousCheckerFactory()

