
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from pyunit import unittest

from twisted.words import service
from twisted.internet import app

class WordsTestCase(unittest.TestCase):
    def testWords(self):
        a = app.Application("testwords")
        s = service.Service('twisted.words',a)
        s.createParticipant("glyph")
        s.createParticipant("sean")
        # XXX OBSOLETE: should be async getPerspectiveRequest
        glyph = s.getPerspectiveNamed("glyph")
        sean = s.getPerspectiveNamed("sean")
        glyph.addContact("sean")


testCases = [WordsTestCase]
