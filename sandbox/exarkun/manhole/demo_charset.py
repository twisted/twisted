
import tokenize, token

import insults
import manhole

TOP_LEFT_CORNER = chr(108)
TOP_RIGHT_CORNER = chr(107)
BOTTOM_LEFT_CORNER = chr(109)
BOTTOM_RIGHT_CORNER = chr(106)

HORIZONTAL_MIDDLE = chr(113)

class TipsInterpreter(manhole.ColoredManhole):
    width = 80
    height = 24

    tipsmode = 'normal'

    def drawingMode(self):
        self.transport.selectCharacterSet(insults.CS_DRAWING, insults.G0)

    def normalMode(self):
        self.transport.selectCharacterSet(insults.CS_US, insults.G0)

    def showCompletions(self):
        completions = [n
                       for n in dir(self.completionObj)
                       if n.startswith(self.completionPrefix)]
        useCompletions = completions[slice(*self.completionRange)]
        self.drawCompletionBox(useCompletions)

    def drawCompletionBox(self, words):
        width = max(map(len, words))
        self.transport.saveCursor()
        self.drawingMode()
        self.transport.cursorUp(len(words) + 2)
        self.transport.write(TOP_LEFT_CORNER +
                             HORIZONTAL_MIDDLE * width +
                             TOP_RIGHT_CORNER)
        self.transport.cursorBackward(width + 2)
        self.transport.cursorDown()
        for w in words:
            self.transport.write('|' +
                                 w +
                                 ' ' * width - len(w) +
                                 '|')
            self.transport.cursorBackward(width + 2)
            self.transport.cursorDown()
        self.transport.write(BOTTOM_LEFT_CORNER +
                             HORIZONTAL_MIDDLE * width +
                             BOTTOM_RIGHT_CORNER)
        self.restoreCursor()

    def getTokens(self):
        L = []
        source = self.getSource()
        t = tokenize.tokenize(s.readline, L.append)
        return L

    def connectionMade(self):
        manhole.ColoredManhole.connectionMade(self)
        t = self.transport
        self.keyHandlers.update({
            '\r': self.handle_ENTER,
            '\n': self.handle_ENTER,

            t.TAB: self.handle_TAB,
            t.UP_ARROW: self.handle_UP,
            t.DOWN_ARROW: self.handle_DOWN})

    def characterReceived(self, ch):
        newmode = getattr(self, 'tipsmode_' + self.tipsmode)(ch)
        if newmode is not None:
            self.tipsmode = newmode

    def tipsmode_normal(self, ch):
        manhole.ColoredManhole.characterReceived(self, ch)

        # Yea this is duplicate effort, but factoring things well
        # enough to let them share the results of tokenization is
        # a task for another day.
        L = self.getTokens()

        # If the last token is a '.', check out the name immediately
        # preceding it.
        if len(L) > 2:
            if L[-1][0] == token.DOT:
                if L[-2][0] == token.NAME:
                    name = L[-2][1]
                    if name in self.locals:
                        self.completionSelection = 0
                        self.completionRange = (0, 5)
                        self.completionPrefix = ''
                        self.completionName = name
                        self.completionObj = self.locals[name]
                        self.showCompletions()
                        return 'completion'

    def tipsmode_completion(self, ch):
        manhole.ColoredManhole.characterReceived(self, ch)

        L = self.getTokens()
        if L[-1][0] != token.NAME:
            # Completion is over, baby.
            del (self.completionSelection, self.completionRange,
                 self.completionPrefix, self.completionName,
                 self.completionObj)
            self.eraseCompletions()
            return 'normal'
        else:
            # Refresh the completions list
            self.updateCompletions()


from twisted.application import service
application = service.Application("Charset Demo App")

from demolib import makeService
makeService({'protocolFactory': DemoCharsets,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
