# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import classProvides

from twisted.plugin import IPlugin

from twisted.application.service import ServiceMaker
from twisted.words import iwords


NewTwistedWords = ServiceMaker(
    "New Twisted Words",
    "twisted.words.tap",
    "A modern words server",
    "words")

TwistedXMPPRouter = ServiceMaker(
    "XMPP Router",
    "twisted.words.xmpproutertap",
    "An XMPP Router server",
    "xmpp-router")

class RelayChatInterface(object):
    classProvides(IPlugin, iwords.IProtocolPlugin)

    name = 'irc'

    def getFactory(cls, realm, portal):
        from twisted.words import service
        return service.IRCFactory(realm, portal)
    getFactory = classmethod(getFactory)

class PBChatInterface(object):
    classProvides(IPlugin, iwords.IProtocolPlugin)

    name = 'pb'

    def getFactory(cls, realm, portal):
        from twisted.spread import pb
        return pb.PBServerFactory(portal, True)
    getFactory = classmethod(getFactory)

