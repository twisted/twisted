#!/usr/bin/env python
# -*- test-case-name: twisted.mail.test.test_pop3client -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.internet.protocol import Factory
from twisted.protocols import basic
from twisted.internet import reactor
import sys

USER = "test"
PASS = "twisted"

PORT = 1100

SSL_SUPPORT = True
UIDL_SUPPORT = True
INVALID_SERVER_RESPONSE = False
INVALID_CAPABILITY_RESPONSE = False
INVALID_LOGIN_RESPONSE = False
DENY_CONNECTION = False
DROP_CONNECTION = False
BAD_TLS_RESPONSE = False
TIMEOUT_RESPONSE = False
TIMEOUT_DEFERRED = False
SLOW_GREETING = False

"""Commands"""
CONNECTION_MADE = "+OK POP3 localhost v2003.83 server ready"

CAPABILITIES = [
"TOP",
"LOGIN-DELAY 180",
"USER",
"SASL LOGIN"
]

CAPABILITIES_SSL = "STLS"
CAPABILITIES_UIDL = "UIDL"

 
INVALID_RESPONSE = "-ERR Unknown request"
VALID_RESPONSE = "+OK Command Completed"
AUTH_DECLINED = "-ERR LOGIN failed"
AUTH_ACCEPTED = "+OK Mailbox open, 0 messages"
TLS_ERROR = "-ERR server side error start TLS handshake"
LOGOUT_COMPLETE = "+OK quit completed"
NOT_LOGGED_IN = "-ERR Unknown AUHORIZATION state command"
STAT = "+OK 0 0"
UIDL = "+OK Unique-ID listing follows\r\n."
LIST = "+OK Mailbox scan listing follows\r\n."
CAP_START = "+OK Capability list follows:"


class POP3TestServer(basic.LineReceiver):
    def __init__(self, contextFactory = None):
        self.loggedIn = False
        self.caps = None
        self.tmpUser = None
        self.ctx = contextFactory

    def sendSTATResp(self, req):
        self.sendLine(STAT)

    def sendUIDLResp(self, req):
        self.sendLine(UIDL)

    def sendLISTResp(self, req):
        self.sendLine(LIST)

    def sendCapabilities(self):
        if self.caps is None:
            self.caps = [CAP_START]

        if UIDL_SUPPORT:
            self.caps.append(CAPABILITIES_UIDL)

        if SSL_SUPPORT:
            self.caps.append(CAPABILITIES_SSL)

        for cap in CAPABILITIES:
            self.caps.append(cap)
        resp = '\r\n'.join(self.caps)
        resp += "\r\n."

        self.sendLine(resp)


    def connectionMade(self):
        if DENY_CONNECTION:
            self.disconnect()
            return

        if SLOW_GREETING:
            reactor.callLater(20, self.sendGreeting)

        else:
            self.sendGreeting()

    def sendGreeting(self):
        self.sendLine(CONNECTION_MADE)

    def lineReceived(self, line):
        """Error Conditions"""

        uline = line.upper()
        find = lambda s: uline.find(s) != -1

        if TIMEOUT_RESPONSE:
            # Do not respond to clients request
            return

        if DROP_CONNECTION:
            self.disconnect()
            return

        elif find("CAPA"):
            if INVALID_CAPABILITY_RESPONSE:
                self.sendLine(INVALID_RESPONSE)
            else:
                self.sendCapabilities()

        elif find("STLS") and SSL_SUPPORT:
            self.startTLS()

        elif find("USER"):
            if INVALID_LOGIN_RESPONSE:
                self.sendLine(INVALID_RESPONSE)
                return

            resp = None
            try:
                self.tmpUser = line.split(" ")[1]
                resp = VALID_RESPONSE
            except:
                resp = AUTH_DECLINED

            self.sendLine(resp)

        elif find("PASS"):
            resp = None
            try:
                pwd = line.split(" ")[1]

                if self.tmpUser is None or pwd is None:
                    resp = AUTH_DECLINED
                elif self.tmpUser == USER and pwd == PASS:
                    resp = AUTH_ACCEPTED
                    self.loggedIn = True
                else:
                    resp = AUTH_DECLINED
            except:
                resp = AUTH_DECLINED

            self.sendLine(resp)

        elif find("QUIT"):
            self.loggedIn = False
            self.sendLine(LOGOUT_COMPLETE)
            self.disconnect()

        elif INVALID_SERVER_RESPONSE:
            self.sendLine(INVALID_RESPONSE)

        elif not self.loggedIn:
            self.sendLine(NOT_LOGGED_IN)

        elif find("NOOP"):
            self.sendLine(VALID_RESPONSE)

        elif find("STAT"):
            if TIMEOUT_DEFERRED:
                return
            self.sendLine(STAT)

        elif find("LIST"):
            if TIMEOUT_DEFERRED:
                return
            self.sendLine(LIST)

        elif find("UIDL"):
            if TIMEOUT_DEFERRED:
                return
            elif not UIDL_SUPPORT:
                self.sendLine(INVALID_RESPONSE)
                return

            self.sendLine(UIDL)

    def startTLS(self):
        if self.ctx is None:
            self.getContext()

        if SSL_SUPPORT and self.ctx is not None:
            self.sendLine('+OK Begin TLS negotiation now')
            self.transport.startTLS(self.ctx)
        else:
            self.sendLine('-ERR TLS not available')

    def disconnect(self):
        self.transport.loseConnection()

    def getContext(self):
        try:
            from twisted.internet import ssl
        except ImportError:
           self.ctx = None
        else:
            self.ctx = ssl.ClientContextFactory()
            self.ctx.method = ssl.SSL.TLSv1_METHOD


usage = """popServer.py [arg] (default is Standard POP Server with no messages)
no_ssl  - Start with no SSL support
no_uidl - Start with no UIDL support
bad_resp - Send a non-RFC compliant response to the Client
bad_cap_resp - send a non-RFC compliant response when the Client sends a 'CAPABILITY' request
bad_login_resp - send a non-RFC compliant response when the Client sends a 'LOGIN' request
deny - Deny the connection
drop - Drop the connection after sending the greeting
bad_tls - Send a bad response to a STARTTLS
timeout - Do not return a response to a Client request
to_deferred - Do not return a response on a 'Select' request. This
              will test Deferred callback handling
slow - Wait 20 seconds after the connection is made to return a Server Greeting
"""

def printMessage(msg):
    print("Server Starting in %s mode" % msg)

def processArg(arg):

    if arg.lower() == 'no_ssl':
        global SSL_SUPPORT
        SSL_SUPPORT = False
        printMessage("NON-SSL")

    elif arg.lower() == 'no_uidl':
        global UIDL_SUPPORT
        UIDL_SUPPORT = False
        printMessage("NON-UIDL")

    elif arg.lower() == 'bad_resp':
        global INVALID_SERVER_RESPONSE
        INVALID_SERVER_RESPONSE = True
        printMessage("Invalid Server Response")

    elif arg.lower() == 'bad_cap_resp':
        global INVALID_CAPABILITY_RESPONSE
        INVALID_CAPABILITY_RESPONSE = True
        printMessage("Invalid Capability Response")

    elif arg.lower() == 'bad_login_resp':
        global INVALID_LOGIN_RESPONSE
        INVALID_LOGIN_RESPONSE = True
        printMessage("Invalid Capability Response")

    elif arg.lower() == 'deny':
        global DENY_CONNECTION
        DENY_CONNECTION = True
        printMessage("Deny Connection")

    elif arg.lower() == 'drop':
        global DROP_CONNECTION
        DROP_CONNECTION = True
        printMessage("Drop Connection")


    elif arg.lower() == 'bad_tls':
        global BAD_TLS_RESPONSE
        BAD_TLS_RESPONSE = True
        printMessage("Bad TLS Response")

    elif arg.lower() == 'timeout':
        global TIMEOUT_RESPONSE
        TIMEOUT_RESPONSE = True
        printMessage("Timeout Response")

    elif arg.lower() == 'to_deferred':
        global TIMEOUT_DEFERRED
        TIMEOUT_DEFERRED = True
        printMessage("Timeout Deferred Response")

    elif arg.lower() == 'slow':
        global SLOW_GREETING
        SLOW_GREETING = True
        printMessage("Slow Greeting")

    elif arg.lower() == '--help':
        print(usage)
        sys.exit()

    else:
        print(usage)
        sys.exit()

def main():

    if len(sys.argv) < 2:
        printMessage("POP3 with no messages")
    else:
        args = sys.argv[1:]

        for arg in args:
            processArg(arg)

    f = Factory()
    f.protocol = POP3TestServer
    reactor.listenTCP(PORT, f)
    reactor.run()

if __name__ == '__main__':
    main()
