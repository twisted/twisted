# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from zope.interface import classProvides
from twisted.python.components import backwardsCompatImplements

from twisted.plugin import IPlugin

from twisted.scripts.mktap import _tapHelper
from twisted.application import service, compat
from twisted.python.reflect import namedAny
from twisted.words import botbot

class _ancientTAPHelper(_tapHelper):
    def makeService(self, options):
        ser = service.MultiService()
        oldapp = compat.IOldApplication(ser)
        oldapp.name = "Twisted Words"
        namedAny(self.module).updateApplication(oldapp, options)
        return ser

TwistedWords = _ancientTAPHelper(
    "Twisted Words",
    "twisted.words.tap",
    "A chat service.",
    "words")

TwistedTOC = _tapHelper(
    "Twisted TOC Server",
    "twisted.words.toctap",
    "An AIM TOC service.",
    "toc")

class WordsBot:
    classProvides(IPlugin, botbot.IBotBot)

    name = "Bot-Creating Bot"
    botType = "botbot"

    def createBot():
        return botbot.createBot()
    createBot = staticmethod(createBot)
backwardsCompatImplements(WordsBot)
