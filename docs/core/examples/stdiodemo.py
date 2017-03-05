#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Example using stdio, Deferreds, LineReceiver and twisted.web.client.

Note that the WebCheckerCommandProtocol protocol could easily be used in e.g.
a telnet server instead; see the comments for details.

Based on an example by Abe Fettig.
"""

from twisted.internet import stdio, reactor
from twisted.protocols import basic
from twisted.web import client

class WebCheckerCommandProtocol(basic.LineReceiver):
    delimiter = '\n' # unix terminal style newlines. remove this line
                     # for use with Telnet

    def connectionMade(self):
        self.sendLine("Web checker console. Type 'help' for help.")

    def lineReceived(self, line):
        # Ignore blank lines
        if not line: return

        # Parse the command
        commandParts = line.split()
        command = commandParts[0].lower()
        args = commandParts[1:]

        # Dispatch the command to the appropriate method.  Note that all you
        # need to do to implement a new command is add another do_* method.
        try:
            method = getattr(self, 'do_' + command)
        except AttributeError as e:
            self.sendLine('Error: no such command.')
        else:
            try:
                method(*args)
            except Exception as e:
                self.sendLine('Error: ' + str(e))

    def do_help(self, command=None):
        """help [command]: List commands, or show help on the given command"""
        if command:
            self.sendLine(getattr(self, 'do_' + command).__doc__)
        else:
            commands = [cmd[3:] for cmd in dir(self) if cmd.startswith('do_')]
            self.sendLine("Valid commands: " +" ".join(commands))

    def do_quit(self):
        """quit: Quit this session"""
        self.sendLine('Goodbye.')
        self.transport.loseConnection()
        
    def do_check(self, url):
        """check <url>: Attempt to download the given web page"""
        client.Agent(reactor).request('GET', url).addCallback(
            client.readBody).addCallback(
            self.__checkSuccess).addErrback(
            self.__checkFailure)

    def __checkSuccess(self, pageData):
        self.sendLine("Success: got %i bytes." % len(pageData))

    def __checkFailure(self, failure):
        self.sendLine("Failure: " + failure.getErrorMessage())

    def connectionLost(self, reason):
        # stop the reactor, only because this is meant to be run in Stdio.
        reactor.stop()

if __name__ == "__main__":
    stdio.StandardIO(WebCheckerCommandProtocol())
    reactor.run()
