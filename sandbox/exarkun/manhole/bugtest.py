
# Based on jknight's vt100 bug test suite
# Comments are copied verbatim.  Individual tests are translated from C
# as closely as possible.

import insults

from twisted.internet import defer, reactor

class BugTester(insults.TerminalListener):
    width = 80
    height = 24

    def __init__(self, proto):
        self.proto = proto
        self.proto.reset()
        self.proto.eraseDisplay()

        defer.succeed(None
            ).addCallback(self.testAutowrap
            ).addCallback(self.testMargins_a
            ).addCallback(self.testMargins_b
            ).addCallback(self.testScroll
            ).addCallback(self.reportResults
            ).addCallback(lambda r: proto.disconnect()
            )

        self.failed = []
        self.passed = []

    def reportResults(self, _=None):
        self.proto.cursorPosition(2, self.height / 2)
        self.proto.write('Passed: ' + (',' .join(self.passed) or 'None') + '\n')
        self.proto.cursorPosition(2, self.height / 2 + 1)
        self.proto.write('Failed: ' + (','.join(self.failed) or 'None') + '\n')

        d = defer.Deferred()
        reactor.callLater(5, d.callback, None)
        return d

    def terminalSize(self, width, height):
        self.width = width
        self.height = height

    # known bug #1a: AUTOWRAP, bettertelnet 2.0fc1
    # when cursor is in the right column, it incorrectly wraps sometimes
    # even when not inserting a new character.

    # known bug #1b: AUTOWRAP, actual VT100s (?), and many emulators
    # after writing the 80th character the cursor is still in the 80th
    # column, but a "wrap next character" flag is set.
    # Thus doing "\e[K" (erase after cursor in line) will the 80th char.
    # when it should not.
    def testAutowrap(self, _=None):
        self.proto.cursorPosition(0, self.height - 2)
        self.proto.write(" " * self.width)
        self.proto.eraseToLineEnd()

        def cbCursorPosition((x, y), width, height):
            if x != width or y != height - 2:
                self.failed.append('Autowrap')
            else:
                self.passed.append('Autowrap')

        return self.proto.reportCursorPosition(
            ).addCallback(cbCursorPosition, self.width, self.height
            )

    # known bug #2: MARGINS_1,  win2k telnet
    # \n below bottom margin scrolls scroll area in windows telnet
    # instead of going to next line outside scroll area
    def testMargins_a(self, _=None):
        self.proto.cursorPosition(0, self.height - 2)
        self.proto.write('\n\r')

        def cbCursorPosition((x, y), width, height):
            if x != 0 or y != height - 1:
                self.failed.append('Margins_a')
            else:
                self.passed.append('Margins_a')

        return self.proto.reportCursorPosition(
            ).addCallback(cbCursorPosition, self.width, self.height
            )

    # known bug #3: MARGINS_2, bettertelnet 2.0fc1
    # cursor down below bottom margin teleports cursor back into scroll area
    # (what kind of crack was he smoking??)
    def testMargins_b(self, _=None):
        self.proto.setScrollRegion(0, self.height - 3)
        self.proto.cursorPosition(0, self.height - 2)
        self.proto.cursorDown()

        def cbCursorPosition((x, y), width, height):
            if x != 0 or y != self.height - 1:
                self.failed.append('Margins_b')
            else:
                self.passed.append('Margins_b')

        return self.proto.reportCursorPosition(
            ).addCallback(cbCursorPosition, self.width, self.height
            )

    # #4: windows telnet (sux): \e[r (clear scroll window) doesn't do anything
    # must use \e[1;<height>r instead.
    def testScroll(self, _=None):
        pass

from twisted.application import service
application = service.Application("Terminal Compatibility Test")

from demolib import makeService
makeService({'handler': BugTester,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
