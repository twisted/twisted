"""TELNET implementation, with line-oriented command handling.
"""


# System Imports
import string, copy, traceback, sys
from cStringIO import StringIO


# Twisted Imports
from twisted import copyright
from twisted.python import log

# Sibling Imports
import protocol

# Some utility chars.

ESC =            chr(27) # ESC for doing fanciness
BOLD_MODE_ON =   ESC+"[1m" # turn bold on
BOLD_MODE_OFF=   ESC+"[m"  # no char attributes


# Characters gleaned from the various (and conflicting) RFCs.  Not all of these are correct.

NULL =            chr(0)  # No operation.
LF   =           chr(10)  # Moves the printer to the
                          # next print line, keeping the
                          # same horizontal position.
CR =             chr(13)  # Moves the printer to the left
                          # margin of the current line.
BEL =             chr(7)  # Produces an audible or
                          # visible signal (which does
                          # NOT move the print head).
BS  =             chr(8)  # Moves the print head one
                          # character position towards
                          # the left margin.
HT  =             chr(9)  # Moves the printer to the
                          # next horizontal tab stop.
                          # It remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
VT =             chr(11)  # Moves the printer to the
                          # next vertical tab stop.  It
                          # remains unspecified how
                          # either party determines or
                          # establishes where such tab
                          # stops are located.
FF =             chr(12)  # Moves the printer to the top
                          # of the next page, keeping
                          # the same horizontal position.
SE =            chr(240)  # End of subnegotiation parameters.
NOP=            chr(241)  # No operation.
DM =            chr(242)  # "Data Mark": The data stream portion
                          # of a Synch.  This should always be
                          # accompanied by a TCP Urgent
                          # notification.
BRK=            chr(243)  # NVT character Break.
IP =            chr(244)  # The function Interrupt Process.
AO =            chr(245)  # The function Abort Output
AYT=            chr(246)  # The function Are You There.
EC =            chr(247)  # The function Erase Character.
EL =            chr(248)  # The function Erase Line
GA =            chr(249)  # The Go Ahead signal.
SB =            chr(250)  # Indicates that what follows is
                          # subnegotiation of the indicated
                          # option.
WILL =          chr(251)  # Indicates the desire to begin
                          # performing, or confirmation that
                          # you are now performing, the
                          # indicated option.
WONT =          chr(252)  # Indicates the refusal to perform,
                          # or continue performing, the
                          # indicated option.
DO =            chr(253)  # Indicates the request that the
                          # other party perform, or
                          # confirmation that you are expecting
                          # the other party to perform, the
                          # indicated option.
DONT =          chr(254)  # Indicates the demand that the
                          # other party stop performing,
                          # or confirmation that you are no
                          # longer expecting the other party
                          # to perform, the indicated option.
IAC =           chr(255)  # Data Byte 255.

# features

ECHO  =           chr(1)  # User-to-Server:  Asks the server to send
                          # Echos of the transmitted data.

                          # Server-to User:  States that the server is
                          # sending echos of the transmitted data.
                          # Sent only as a reply to ECHO or NO ECHO.

SUPGA =           chr(3)  # Supress Go Ahead...? "Modern" telnet servers
                          # are supposed to do this.

LINEMODE =       chr(34)  # I don't care that Jon Postel is dead.

HIDE  =         chr(133)  # The intention is that a server will send
                          # this signal to a user system which is
                          # echoing locally (to the user) when the user
                          # is about to type something secret (e.g. a
                          # password).  In this case, the user system
                          # is to suppress local echoing or overprint
                          # the input (or something) until the server
                          # sends a NOECHO signal.  In situations where
                          # the user system is not echoing locally,
                          # this signal must not be sent by the server.


NOECHO=         chr(131)  # User-to-Server:  Asks the server not to
                          # return Echos of the transmitted data.
                          # 
                          # Server-to-User:  States that the server is
                          # not sending echos of the transmitted data.
                          # Sent only as a reply to ECHO or NO ECHO,
                          # or to end the hide your input.



iacBytes = {
    DO:   'DO',
    DONT: 'DONT',
    WILL: 'WILL',
    WONT: 'WONT',
    IP:   'IP'
    }

def multireplace(st, dct):
    for k, v in dct.items():
        st = string.replace(st, k, v)
    return st

class Telnet(protocol.Protocol):

    gotIAC = 0
    iacByte = None
    lastLine = None
    buffer = ''
    echo = 0
    mode = "User"

    def connectionMade(self):
        self.transport.write(self.welcomeMessage() + self.loginPrompt())

    def welcomeMessage(self):
        x = self.factory.__class__
        return ("\r\n" + x.__module__ + '.' + x.__name__ +
                '\r\nTwisted %s\r\n' % copyright.version
                )

    def loginPrompt(self):
        return "username: "

    def iacDO(self, feature):
        pass

    def iacDONT(self, feature):
        pass

    def iacWILL(self, feature):
        pass

    def iacWONT(self, feature):
        pass

    def iacSBchunk(self, chunk):
        pass

    def iacIP(self, feature):
        self.goodBye()

    def goodBye(self):
        pass

    def processLine(self, line):
        self.mode = getattr(self, "process"+self.mode)(line)

    def processUser(self, user):
        self.username = user
        self.transport.write(IAC+WILL+ECHO+"password: ")
        return "Password"

    def processPassword(self, paswd):
        self.transport.write(IAC+WONT+ECHO+"*****\r\n")
        if not self.authenticate(self.username, paswd):
            return "Done"
        return "Command"

    def processCommand(self, cmd):
        return "Command"

    def processChunk(self, chunk):
        self.buffer = self.buffer + chunk
        idx = string.find(self.buffer,'\r\n')
        if idx == -1:
            idx = string.find(self.buffer, '\r\000')
        if idx != -1:
            buf, self.buffer = self.buffer[:idx], self.buffer[idx+2:]
            self.processLine(buf)
            if self.mode == 'Done':
                self.transport.loseConnection()

    def dataReceived(self, data):
        chunk = StringIO()
        # silly little IAC state-machine
        for char in data:
            if self.gotIAC:
                # working on an IAC request state
                if self.iacByte:
                    # we're in SB mode, getting a chunk
                    if self.iacByte == SB:
                        if char == SE:
                            self.iacSBchunk(chunk.getvalue())
                            chunk = StringIO()
                            del self.iacByte
                            del self.gotIAC
                        else:
                            chunk.write(char)
                    else:
                        # got all I need to know state
                        try:
                            getattr(self, 'iac'+iacBytes[self.iacByte])(char)
                        except KeyError:
                            pass
                        del self.iacByte
                        del self.gotIAC
                else:
                    # got IAC, this is my W/W/D/D (or perhaps sb)
                    self.iacByte = char
            elif char == IAC:
                # Process what I've got so far before going into
                # the IAC state; don't want to process characters
                # in an inconsistent state with what they were
                # received in.
                c = chunk.getvalue()
                if c:
                    why = self.processChunk(c)
                    if why:
                        return why
                    chunk = StringIO()
                self.gotIAC = 1
            else:
                chunk.write(char)
        # chunks are of a relatively indeterminate size.
        c = chunk.getvalue()
        if c:
            why = self.processChunk(c)
            if why:
                return why


class Shell(Telnet):

    def authenticate(self, username, password):
        return ((self.factory.username == username) and
                (password == self.factory.password))

    def processCommand(self, cmd):
        fn = '$telnet$'
        try:
            code = compile(cmd,fn,'eval')
        except:
            try:
                code = compile(cmd, fn, 'single')
            except:
                io = StringIO()
                traceback.print_exc(file=io)
                self.transport.write(io.getvalue()+'\r\n')
                return "Command"
        try:
            val, output = log.output(eval, code, self.factory.namespace)
            self.transport.write(output)

            if val is not None:
                self.transport.write(repr(val))
            self.transport.write('\r\n')
        except:
            io = StringIO()
            traceback.print_exc(file=io)
            self.transport.write(io.getvalue()+'\r\n')

        return "Command"


class ShellFactory(protocol.Factory):
    username = "admin"
    password = "admin"

    def __init__(self):
        self.namespace = {}

    def __getstate__(self):
        """This returns the persistent state of this shell factory.
        """
        # TODO -- refactor this and twisted.reality.author.Author to use common
        # functionality (perhaps the 'code' module?)
        dict = self.__dict__
        ns = copy.copy(dict['namespace'])
        dict['namespace'] = ns
        if ns.has_key('__builtins__'):
            del ns['__builtins__']
        return dict

    def buildProtocol(self, addr):
        p = Shell()
        p.factory = self
        return p
        
