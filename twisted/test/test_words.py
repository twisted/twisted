from pyunit import unittest

from twisted.words import service
from twisted.internet import main

class WordsTestCase(unittest.TestCase):
    def testWords(self):
        a = main.Application("testwords")
        s = service.Service('twisted.words',a)
        s.addParticipant("glyph")
        s.addParticipant("sean")
        glyph = s.getPerspectiveNamed("glyph")
        sean = s.getPerspectiveNamed("sean")
        glyph.addContact("sean")


testCases = [WordsTestCase]
