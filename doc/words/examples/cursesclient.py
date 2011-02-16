#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This is an example of integrating curses with the twisted underlying    
select loop. Most of what is in this is insignificant -- the main piece 
of interest is the 'CursesStdIO' class.                                 

This class acts as file-descriptor 0, and is scheduled with the twisted
select loop via reactor.addReader (once the curses class extends it
of course). When there is input waiting doRead is called, and any
input-oriented curses calls (ie. getch()) should be executed within this
block.

Remember to call nodelay(1) in curses, to make getch() non-blocking.
"""

# System Imports
import curses, time, traceback, sys
import curses.wrapper

# Twisted imports
from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.words.protocols.irc import IRCClient
from twisted.python import log

class TextTooLongError(Exception):
    pass

class CursesStdIO:
    """fake fd to be registered as a reader with the twisted reactor.
       Curses classes needing input should extend this"""

    def fileno(self):
        """ We want to select on FD 0 """
        return 0

    def doRead(self):
        """called when input is ready"""

    def logPrefix(self): return 'CursesClient'


class IRC(IRCClient):

    """ A protocol object for IRC """

    nickname = "testcurses"

    def __init__(self, screenObj):
        # screenObj should be 'stdscr' or a curses window/pad object
        self.screenObj = screenObj
        # for testing (hacky way around initial bad design for this example) :)
        self.screenObj.irc = self

    def lineReceived(self, line):
        """ When receiving a line, add it to the output buffer """
        self.screenObj.addLine(line)

    def connectionMade(self):
        IRCClient.connectionMade(self)
        self.screenObj.addLine("* CONNECTED")

    def clientConnectionLost(self, connection, reason):
        pass


class IRCFactory(ClientFactory):

    """
    Factory used for creating IRC protocol objects 
    """

    protocol = IRC

    def __init__(self, screenObj):
        self.irc = self.protocol(screenObj)

    def buildProtocol(self, addr=None):
        return self.irc

    def clientConnectionLost(self, conn, reason):
        pass


class Screen(CursesStdIO):
    def __init__(self, stdscr):
        self.timer = 0
        self.statusText = "TEST CURSES APP -"
        self.searchText = ''
        self.stdscr = stdscr

        # set screen attributes
        self.stdscr.nodelay(1) # this is used to make input calls non-blocking
        curses.cbreak()
        self.stdscr.keypad(1)
        curses.curs_set(0)     # no annoying mouse cursor

        self.rows, self.cols = self.stdscr.getmaxyx()
        self.lines = []

        curses.start_color()

        # create color pair's 1 and 2
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)

        self.paintStatus(self.statusText)

    def connectionLost(self, reason):
        self.close()

    def addLine(self, text):
        """ add a line to the internal list of lines"""

        self.lines.append(text)
        self.redisplayLines()

    def redisplayLines(self):
        """ method for redisplaying lines 
            based on internal list of lines """

        self.stdscr.clear()
        self.paintStatus(self.statusText)
        i = 0
        index = len(self.lines) - 1
        while i < (self.rows - 3) and index >= 0:
            self.stdscr.addstr(self.rows - 3 - i, 0, self.lines[index], 
                               curses.color_pair(2))
            i = i + 1
            index = index - 1
        self.stdscr.refresh()

    def paintStatus(self, text):
        if len(text) > self.cols: raise TextTooLongError
        self.stdscr.addstr(self.rows-2,0,text + ' ' * (self.cols-len(text)), 
                           curses.color_pair(1))
        # move cursor to input line
        self.stdscr.move(self.rows-1, self.cols-1)

    def doRead(self):
        """ Input is ready! """
        curses.noecho()
        self.timer = self.timer + 1
        c = self.stdscr.getch() # read a character

        if c == curses.KEY_BACKSPACE:
            self.searchText = self.searchText[:-1]

        elif c == curses.KEY_ENTER or c == 10:
            self.addLine(self.searchText)
            # for testing too
            try: self.irc.sendLine(self.searchText)
            except: pass
            self.stdscr.refresh()
            self.searchText = ''

        else:
            if len(self.searchText) == self.cols-2: return
            self.searchText = self.searchText + chr(c)

        self.stdscr.addstr(self.rows-1, 0, 
                           self.searchText + (' ' * (
                           self.cols-len(self.searchText)-2)))
        self.stdscr.move(self.rows-1, len(self.searchText))
        self.paintStatus(self.statusText + ' %d' % len(self.searchText))
        self.stdscr.refresh()

    def close(self):
        """ clean up """

        curses.nocbreak()
        self.stdscr.keypad(0)
        curses.echo()
        curses.endwin()

if __name__ == '__main__':
    stdscr = curses.initscr() # initialize curses
    screen = Screen(stdscr)   # create Screen object
    stdscr.refresh()
    ircFactory = IRCFactory(screen)
    reactor.addReader(screen) # add screen object as a reader to the reactor
    reactor.connectTCP("irc.freenode.net",6667,ircFactory) # connect to IRC
    reactor.run() # have fun!
    screen.close()
