#! /usr/bin/python

import sys, re
from twisted.internet import reactor
from twisted.internet.stdio import StandardIO
from twisted.spread import pb
from twisted.protocols.basic import LineReceiver
from go_server import GoGameError

class PlayerInput(LineReceiver):
    delimiter = '\n'
    def __init__(self, player):
        #LineReceiver.__init__(self)   # LineReceiver has no __init__ method
        self.player = player
        self.player.input = self
    def connectionMade(self):
        self.printPrompt()
    def printPrompt(self):
        self.transport.write("command : ")
    def lineReceived(self, line):
        self.player.parseCommand(line)
        
    

class Player:
    def __init__(self):
        self.input = None
        self.showCommands()

    def showCommands(self):
        print "valid commands:"
        print " join name passwd side   (where side is 'black' or 'white')"
        print " move x,y   (where x and y are 0 .. 18)"
        
    def connect(self, name, passwd, side):
        self.d = pb.connect("localhost", 8800, name, passwd, "goservice",
                            side)
        self.d.addCallback(self.join)
        self.d.addErrback(self.join_failed)
    def join(self, perspective):
        self.p = perspective
        print " game joined"
        #self.p.callRemote('getBoard').addCallback(self.printBoard)
        self.input.printPrompt()
    def join_failed(self, why):
        t = why.type
        print "t", t, type(t)
        print "check", why.check(GoGameError)
        print " failed:", why.getErrorMessage()
        self.input.printPrompt()

    def newBoard(self, board):
        self.board = board
    def printBoard(self, board):
        self.board = board
        print " current board:", board

    def move(self, x, y):
        d = self.p.callRemote('makeMove', x, y)
        d.addCallback(self.moveOk)
        d.addErrback(self.badMove)
    def moveOk(self, result):
        if result == "game over":
            print " Game Over"
            reactor.stop()
            return
        print " move ok"
        self.input.printPrompt()
    def badMove(self, why):
        print " move failed:", why.getErrorMessage()
        self.input.printPrompt()
        
    def parseCommand(self, cmd):
        m = re.search(r'^\s*join\s+(\w+)\s+(\w+)\s+(\w+)', cmd)
        if m:
            self.connect(m.group(1), m.group(2), m.group(3))
            return
        m = re.search(r'^\s*move\s+(\d+)[\s,]+(\d+)', cmd)
        if m:
            self.move(int(m.group(1)), int(m.group(2)))
            return
        print "unknown command '%s'" % cmd
        self.input.printPrompt()
            
def main():
    #p = Player("alice", "sekrit", "black")
    p = Player()
    s = StandardIO(PlayerInput(p))

    reactor.run()

if __name__ == '__main__':
    main()
