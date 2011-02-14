#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Simple PB Words client demo

This connects to a server (host/port specified by argv[1]/argv[2]),
authenticates with a username and password (given by argv[3] and argv[4]),
joins a group (argv[5]) sends a simple message, leaves the group, and quits
the server.
"""

import sys
from twisted.python import log
from twisted.cred import credentials
from twisted.words import service
from twisted.spread import pb
from twisted.internet import reactor

class DemoMind(service.PBMind):
    """An utterly pointless PBMind subclass.

    This notices messages received and prints them to stdout.  Since
    the bot never stays in a channel very long, it is exceedingly
    unlikely this will ever do anything interesting.
    """
    def remote_receive(self, sender, recipient, message):
        print 'Woop', sender, recipient, message

def quitServer(ignored):
    """Quit succeeded, shut down the reactor.
    """
    reactor.stop()

def leftGroup(ignored, avatar):
    """Left the group successfully, quit the server.
    """
    q = avatar.quit()
    q.addCallback(quitServer)
    return q

def sentMessage(ignored, group, avatar):
    """Sent the message successfully, leave the group.
    """
    l = group.leave()
    l.addCallback(leftGroup, avatar)
    return l

def joinedGroup(group, avatar):
    """Joined the group successfully, send a stupid message.
    """
    s = group.send({"text": "Hello, monkeys"})
    s.addCallback(sentMessage, group, avatar)
    return s

def loggedIn(avatar, group):
    """Logged in successfully, join a group.
    """
    j = avatar.join(group)
    j.addCallback(joinedGroup, avatar)
    return j

def errorOccurred(err):
    """Something went awry, log it and shutdown.
    """
    log.err(err)
    try:
        reactor.stop()
    except RuntimeError:
        pass

def run(host, port, username, password, group):
    """Create a mind and factory and set things in motion.
    """
    m = DemoMind()
    f = pb.PBClientFactory()
    f.unsafeTracebacks = True
    l = f.login(credentials.UsernamePassword(username, password), m)
    l.addCallback(loggedIn, group)
    l.addErrback(errorOccurred)
    reactor.connectTCP(host, int(port), f)

def main():
    """
    Set up logging, have the real main function run, and start the reactor.
    """
    if len(sys.argv) != 6:
        raise SystemExit("Usage: %s host port username password group" % (sys.argv[0],))
    log.startLogging(sys.stdout)

    host, port, username, password, group = sys.argv[1:]
    port = int(port)
    username = username.decode(sys.stdin.encoding)
    group = group.decode(sys.stdin.encoding)

    reactor.callWhenRunning(run, host, port, username, password, group)
    reactor.run()

if __name__ == '__main__':
    main()
