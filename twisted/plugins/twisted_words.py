# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import classProvides

from twisted.plugin import IPlugin

from twisted.scripts.mktap import _tapHelper
from twisted.words import iwords

TwistedTOC = _tapHelper(
    "Twisted TOC Server",
    "twisted.words.toctap",
    "An AIM TOC service.",
    "toc")

NewTwistedWords = _tapHelper(
    "New Twisted Words",
    "twisted.words.tap",
    "A modern words server",
    "words")

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

