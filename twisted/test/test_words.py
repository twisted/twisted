from pyunit import unittest

from twisted.words import service

class WordsTestCase(unittest.TestCase):
    def testWords(self):
        s = service.Service()
        s.addParticipant("glyph", "glyph")
        s.addParticipant("sean", "sean")
        glyph = s.getPerspectiveNamed("glyph")
        sean = s.getPerspectiveNamed("sean")
        glyph.addContact("sean")


testCases = [WordsTestCase]
