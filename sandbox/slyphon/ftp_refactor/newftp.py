# -*- test-case-name: twisted.test.test_ftp -*-

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

"""File Transfer Protocol support for Twisted Python.

Stability: semi-stable

Maintainer: U{Andrew Bennetts<mailto:spiv@twistedmatrix.com>}

Future Plans: The server will be re-written.  The goal for the server is that
it should be secure, high-performance, and overloaded with stupid features.
The client is probably fairly final, but should share more code with the
server, and some details could still change.

Warning: The FTP server is probably insecure, don't use it on open networks.

Server TODO:

 * Authorization
   User / Password is stored in a dict (factory.userdict) in plaintext
   Use cred
   Separate USER / PASS from mainloop

 * Ascii-download
   Currently binary only. Ignores TYPE

 * Missing commands
   HELP, REST, STAT, ...

 * Print out directory-specific messages
   As in READMEs etc

 * Testing
   Test at every ftp-program available and on any platform.
   Automated tests

 * Security
   PORT needs to reply correctly if it fails
   The paths are done by os.path; use the "undocumented" module posixpath

 * Etc
   Documentation, Logging, Procedural content, Localization, Telnet PI,
   stop LIST from blocking...
   Highest priority: Resources.

DOCS:

 * Base information: RFC0959
 * Security: RFC2577
"""

from __future__ import nested_scopes


# System Imports
import os
import time
import string
import types
import re
import StringIO
from math import floor

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter
from twisted import internet
from twisted.internet.defer import Deferred, DeferredList, FAILURE
from twisted.python.failure import Failure
from twisted.python import log, components

from twisted.cred import error
from twisted.cred import portal
from twisted.cred import credentials


# response codes

RESTART_MARKER_REPLY                    = 100
SERVICE_READY_IN_N_MINUTES              = 120
DATA_CNX_ALREADY_OPEN_START_XFR         = 125
FILE_STATUS_OK_OPEN_DATA_CNX            = 150

CMD_OK                                  = 200.1
TYPE_SET_OK                             = 200.2
CMD_NOT_IMPLMNTD_SUPERFLUOUS            = 202
SYS_STATUS_OR_HELP_REPLY                = 211
DIR_STATUS                              = 212
FILE_STATUS                             = 213
HELP_MSG                                = 214
NAME_SYS_TYPE                           = 215
SVC_READY_FOR_NEW_USER                  = 220.1
WELCOME_MSG                             = 220.2
SVC_CLOSING_CTRL_CNX                    = 221
GOODBYE_MSG                             = 221
DATA_CNX_OPEN_NO_XFR_IN_PROGRESS        = 225
CLOSING_DATA_CNX                        = 226
TXFR_COMPLETE_OK                        = 226
ENTERING_PASV_MODE                      = 227
ENTERING_EPSV_MODE                      = 229
USR_LOGGED_IN_PROCEED                   = 230.1     # v1 of code 230
GUEST_LOGGED_IN_PROCEED                 = 230.2     # v2 of code 230
REQ_FILE_ACTN_COMPLETED_OK              = 250
PWD_REPLY                               = 257

USR_NAME_OK_NEED_PASS                   = 331.1     # v1 of Code 331
GUEST_NAME_OK_NEED_EMAIL                = 331.2     # v2 of code 331
NEED_ACCT_FOR_LOGIN                     = 332
REQ_FILE_ACTN_PENDING_FURTHER_INFO      = 350

SVC_NOT_AVAIL_CLOSING_CTRL_CNX          = 421
CANT_OPEN_DATA_CNX                      = 425
CNX_CLOSED_TXFR_ABORTED                 = 426
REQ_ACTN_ABRTD_FILE_UNAVAIL             = 450
REQ_ACTN_ABRTD_LOCAL_ERR                = 451
REQ_ACTN_ABRTD_INSUFF_STORAGE           = 452

SYNTAX_ERR                              = 500
SYNTAX_ERR_IN_ARGS                      = 501
CMD_NOT_IMPLMNTD                        = 502
BAD_CMD_SEQ                             = 503
CMD_NOT_IMPLMNTD_FOR_PARAM              = 504
NOT_LOGGED_IN                           = 530.1     # v1 of code 530 - please log in
AUTH_FAILURE                            = 530.2     # v2 of code 530 - authorization failure
NEED_ACCT_FOR_STORING_FILES             = 532
FILE_NOT_FOUND                          = 550.1     # no such file or directory
PRMSSN_DENIED                           = 550.2     # permission denied
PAGE_TYPE_UNK                           = 551
EXCEEDED_STORAGE_ALLOC                  = 552
FILENAME_NOT_ALLOWED                    = 553


RESPONSES = {
    # -- 100's --
    RESTART_MARKER_REPLY:               '110 MARK yyyy-mmmm', # TODO: this must be fixed
    SERVICE_READY_IN_N_MINUTES:         '120 service ready in %s minutes',
    DATA_CNX_ALREADY_OPEN_START_XFR:    '125 Data connection already open, starting transfer',
    FILE_STATUS_OK_OPEN_DATA_CNX:       '150 File status okay; about to open data connection.',

    # -- 200's --
    CMD_OK:                             '200 Command OK',
    TYPE_SET_OK:                        '200 Type set to %s.',
    CMD_NOT_IMPLMNTD_SUPERFLUOUS:       '202 command not implemented, superfluous at this site',
    SYS_STATUS_OR_HELP_REPLY:           '211 system status reply',
    DIR_STATUS:                         '212 %s',
    FILE_STATUS:                        '213 %s',
    HELP_MSG:                           '214 help: %s',
    NAME_SYS_TYPE:                      '215 UNIX Type: L8',
    WELCOME_MSG:                        '220 Welcome, twisted.ftp at your service.',
    SVC_READY_FOR_NEW_USER:             '220 Service ready',
    GOODBYE_MSG:                        '221 Goodbye.',
    DATA_CNX_OPEN_NO_XFR_IN_PROGRESS:   '225 data connection open, no transfer in progress',
    CLOSING_DATA_CNX:                   '226 Abort successful',
    TXFR_COMPLETE_OK:                   '226 Transfer Complete.',
    ENTERING_PASV_MODE:                 '227 Entering Passive Mode',
    ENTERING_EPSV_MODE:                 '229 Entering Extended Passive Mode (|||%s|).', # where is epsv defined in the rfc's?
    USR_LOGGED_IN_PROCEED:              '230 User logged in, proceed',
    GUEST_LOGGED_IN_PROCEED:            '230 Guest login ok, access restrictions apply.',
    REQ_FILE_ACTN_COMPLETED_OK:         '250 Requested File Action Completed OK', #i.e. CWD completed ok
    PWD_REPLY:                          '257 "%s" is current directory.',

    # -- 300's --
    'userotp':                          '331 Response to %s.',  # ???
    USR_NAME_OK_NEED_PASS:              '331 Password required for %s.',
    GUEST_NAME_OK_NEED_EMAIL:           '331 Guest login ok, type your email address as password.',

    # -- 400's --
    SVC_NOT_AVAIL_CLOSING_CTRL_CNX:     '421 Service not available, closing control connection.',
    CANT_OPEN_DATA_CNX:                 "425 Can't open data connection.",
    CNX_CLOSED_TXFR_ABORTED:            '426 Transfer aborted.  Data connection closed.',

    # -- 500's --
    SYNTAX_ERR:                         "500 '%s': syntax error, command not understood.",
    SYNTAX_ERR_IN_ARGS:                 '501 syntax error in argument(s) %s.',
    CMD_NOT_IMPLMNTD:                   "502 command '%s' not implemented",
    BAD_CMD_SEQ:                        '503 Incorrect sequence of commands: %s',
    CMD_NOT_IMPLMNTD_FOR_PARAM:         "504 Not implemented for parameter '%s'.",
    NOT_LOGGED_IN:                      '530 Please login with USER and PASS.',
    AUTH_FAILURE:                       '530 Sorry, Authentication failed. %s',
    NEED_ACCT_FOR_STORING_FILES:        '532 Need an account for storing files',
    FILE_NOT_FOUND:                     '550 %s: No such file or directory.',
    PRMSSN_DENIED:                      '550 %s: Permission denied.',
    EXCEEDED_STORAGE_ALLOC:             '552 requested file action aborted, exceeded file storage allocation',
    FILENAME_NOT_ALLOWED:               '553 requested action not taken, file name not allowed'
}

class DTP(protocol.Protocol):
    """A Client/Server-independent implementation of the DTP-protocol.
    Performs the actions RETR, STOR and LIST. The data transfer will
    start as soon as:
    1) The user has connected 2) the property 'action' has been set. 
    """
    # PI is the telnet-like interface to FTP
    # Will be set to the instance which initiates DTP
    pi = None
    file = None
    filesize = None
    action = ""
    __bufferedData = ''

    def executeAction(self):
        """Initiates a transfer of data.
        Its action is based on self.action, and self.pi.queuedfile
        """
        func = getattr(self, 'action' + self.action, None)
        if func:
            func(self.pi.queuedfile)

    def connectionMade(self):
        "Will start an transfer, if one is queued up, when the client connects"
        self.dtpPort = self.pi.dtpPort
        if self.action:
            self.executeAction()

    def setAction(self, action):
        "Set the action, and if the connected, start the transfer"
        self.action = action
        if self.transport is not None:
            self.executeAction()
        if action == 'STOR':
            self.dataReceived(self.__bufferedData)
            self.__bufferedData = ''

    def connectionLost(self, reason):
        if (self.action == 'STOR') and (self.file):
            self.pi.reply(TXFR_COMPLETE_OK)
        elif self.file is not None:
            if self.file.tell() == self.filesize:
                self.pi.reply(TXFR_COMPLETE_OK)
            else:
                self.pi.reply(CNX_CLOSED_TXFR_ABORTED)
        if self.file is not None:
            self.file.close()

            self.file = None
        self.pi.queuedfile = None
        self.action = None
        if hasattr(self.dtpPort, 'loseConnection'):
            self.dtpPort.loseConnection()
        else:
            self.dtpPort.disconnect()

    #
    #   "RETR"
    #
    def finishRETR(self):
        """Disconnect, and clean up a RETR
        Called by producer when the transfer is done
        """
        self.transport.loseConnection()

    def makeRETRTransport(self):
        transport = self.transport
        transport.finish = self.finishRETR
        return transport
        
    def actionRETR(self, queuedfile):
        "Send the given file to the peer"
        if self.file is None:
            self.file = open(queuedfile, "rb")
            self.filesize = os.path.getsize(queuedfile)
        producer = SendFileTransfer(self.file, self.filesize, self.makeRETRTransport())
        producer.resumeProducing()

    #
    #   "STOR"
    #
    def dataReceived(self, data):
        if (self.action == 'STOR') and (self.file):
            self.file.write(data)
            self.file.flush()
            self.filesize = self.filesize + len(data)
        else:
            self.__bufferedData += data

    def makeSTORTransport(self):
        transport = self.transport
        return transport
        
    def actionSTOR(self, queuedfile):
        "Retrieve a file from peer"
        self.file = open(queuedfile, "wb")
        self.filesize = 0
        transport = self.makeSTORTransport()

    #
    #   'LIST'
    #
    def actionLIST(self, dir):
        """Prints outs the files in the given directory
        Note that the printout is very fake, and only gives the filesize,
        date, time and filename.
        """
        list = os.listdir(dir)
        s = ''
        for a in list:
            ts = a
            ff = os.path.join(dir, ts) # the full filename
            try:
                # os.path.getmtime calls os.stat: os.stat fails w/ an IOError
                # on broken symlinks.  I know there's some way to get the real
                # mtime out, since ls does it, but I haven't had time to figure
                # out how to do it from python.
                mtn = os.path.getmtime(ff)
                fsize = os.path.getsize(ff)
            except OSError:
                mtn = 0
                fsize = 0
            mtime = time.strftime("%b %d %H:%M", time.gmtime(mtn))
            if os.path.isdir(ff):
                diracc = 'd'
            else:
                diracc = '-'    
            s = s + diracc+"r-xr-xr-x    1 twisted twisted %11d" % fsize+' '+mtime+' '+ts+'\r\n'
        self.action = 'RETR'
        self.file = StringIO.StringIO(s)
        self.filesize = len(s)
        #reactor.callLater(0.1, self.executeAction)
        self.executeAction()

    #
    #   'NLST'
    #
    def actionNLST(self, dir):
        s = '\r\n'.join(os.listdir(dir))
        self.file = StringIO.StringIO(s)
        self.filesize = len(s)
        self.action = 'RETR'
        self.executeAction()
        #reactor.callLater(0.1, self.executeAction)

    class DTPFactory(protocol.ClientFactory):
    """The DTP-Factory.
    This class is not completely self-contained.

    from the RFC:
        The data transfer process establishes and manages the data
        connection.  The DTP can be passive or active.
    """
    # a new DTP factory is generated for each action (?)
    dtpClass = DTP
    dtp = None      # The DTP-protocol
    dtpPort = None  # The TCPClient / TCPServer
    action = None

    def createPassiveServer(self):
        """In FTP, this creates a port/address to listen on
        and tells the client to connect to it, Rather than connecting
        *to* the client. useful when dealing with firewalled clients
        """
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.transport.loseConnection()
            self.dtp = None
        # giving 0 will generate a free port
        self.dtpPort = reactor.listenTCP(0, self)
 
    def createActiveServer(self):
        """A direct connection to the client process
        """
        if self.dtp is not None:
            if self.dtp.transport is not None:
                self.dtp.transport.loseConnection()
            self.dtp = None
        self.dtpPort = reactor.connectTCP(self.peerhost, self.peerport, self)

    def buildProtocol(self,addr):
        p = self.dtpClass()
        p.factory = self
        p.pi = self
        self.dtp = p
        if self.action is not None:
            self.dtp.setAction(self.action)
            self.action = None
        return p

class FTPFactory(protocol.Factory):
#    otp = 0
    command         = ''    # wtf?
    allow_anonymous = True
    useranonymous   = 'anonymous'
    thirdparty      = 0
    root            = None  # root/tld set in avatar?
    portal          = None
    protocol        = FTP

    def __init__(self, portal=None):
        self.portal = portal
        import warnings
        warnings.warn("The FTP server is INSECURE, please don't run it on the internet")

    def buildProtocol(self, addr):
        p = protocol.Factory.buildProtocol(self, addr)
        p.protocol = self.protocol
        p.portal = self.portal
        return p

class FTP(basic.LineReceiver, DTPFactory): # Should add policies.TimeoutMixin
    """An FTP server.
    
    This class is unstable (it will be heavily refactored to support dynamic
    content, etc)."""
    root   = None       # root directory
    wd     = None       # Working Directory
    type   = None       # ASCII or Binary 
    peerhost = None     # client ip addr
    peerport = None     # client port
    queuedfile = None

    # The object which will handle logins for us
    portal = None

    # The account object for this connection 
    avatar = None

    def setAction(self, action):
        """Alias for DTP.setAction
        Since there's no guarantee an instance of dtp exists"""
        if self.dtp is not None:
            self.dtp.setAction(action)
        else:
            self.action = action

    def reply(self, key, s = ''):
        if string.find(RESPONSES[key], '%s') > -1:
            if self.debug:
                log.msg(RESPONSES[key] % s + '\r\n')
            self.transport.write(ftp_reply[key] % s + '\r\n')
        else:
            if self.debug:
                log.msg(RESPONSES[key] + '\r\n')
            self.transport.write(RESPONSES[key] + '\r\n')

    #TODO: get rid of _isAuthorized. if user is not logged in
    #      there will be no available self.filesys (the avatar)
    def _isAuthorized(self):
        '''returns True if this session has been authorized, False otherwise
        This must be run in front of all commands except USER, PASS and QUIT
        basically, syntactic sugar
        '''
        return self.avatar != None
        
    def connectionMade(self):
        self.reply(WELCOME_MSG)

    def ftp_QUIT(self, params):
        self.reply(GOODBYE_MSG)
        self.logout()               # run logout for avatar
        self.transport.loseConnection()
    
    def ftp_USER(self, params):
        """Get the login name, and reset the session
        PASS is expected to follow

        from the rfc:
            The argument field is a Telnet string identifying the user.
            The user identification is that which is required by the
            server for access to its file system.  This command will
            normally be the first command transmitted by the user after
            the control connections are made

            This has the effect of flushing any user, password, and account
            information already supplied and beginning the login sequence
            again.  All transfer parameters are unchanged and any file transfer
            in progress is completed under the old access control parameters.
        """
        if params=='':
            return 1
        self.user = string.split(params)[0]
        if self.factory.anonymous and self.user == self.factory.useranonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)
        # Flush settings
        self.passwd = None
        self.type = 'A'
 
    def ftp_PASS(self, params):
        """Authorize the USER and the submitted password

        from the rfc:
            The argument field is a Telnet string specifying the user's
            password.  This command must be immediately preceded by the
            user name command, and, for some sites, completes the user's
            identification for access control.
        """

        # the difference between an Anon login and a User login is 
        # the avatar that will be returned to the callback
        if not self.user:
            self.reply(BAD_CMD_SEQ, 'USER required before PASS')
            return

        # parse password
        self.passwd = params.split()[0] 

        # if this is an anonymous login
        if self.factory.anonymous and self.user == self.factory.useranonymous:
            self.passwd = params
            if self.portal:
                self.portal.login(
                        credentials.Anonymous(), 
                        None, 
                        IFTPUser
                    ).addCallbacks(self._cbAnonLogin, self._ebLogin
                    )
            else:
                # if cred has been set up correctly, this shouldn't happen
                self.reply(AUTH_FAILURE, 'internal server error')

        # otherwise this is a user login
        else:
            if self.portal:
                self.portal.login(
                        credentials.UsernamePassword(self.user, self.passwd),
                        None,
                        IFTPUser
                    ).addCallbacks(self._cbLogin, self.ebLogin
                    )
            else:
                self.reply(AUTH_FAILURE, 'internal server error')

    def _cbAnonLogin(self, (interface, avatar, logout)):
        '''anonymous login'''
        assert interface is IFTPFileSystem
        self.filesys = avatar
        self.logout = logout
        self.reply(GUEST_LOGGED_IN_PROCEED)

    def _cbLogin(self, (interface, avatar, logout)):
        '''authorized user login'''
        assert interface is IFTPFileSystem
        self.filesys = avatar
        self.logout = logout
        self.reply(USR_LOGGED_IN_PROCEED)

    def _ebLogin(self, failure)
        failure.trap(error.UnauthorizedLogin)
        self.reply(AUTH_FAILURE, '')

    def ftp_NOOP(self, params):
        """Do nothing, and reply an OK-message
        Sometimes used by clients to avoid a time-out.
        TODO: Add time-out, let Noop extend this time-out.
        Add a No-Transfer-Time-out as well to get rid of idlers.

        from the rfc:
            This command does not affect any parameters or previously
            entered commands. It specifies no action other than that the
            server send an OK reply.
        """
        if not self._isAuthorized(): return
        self.reply(CMD_OK, 'NOOP')

    def ftp_SYST(self, params):
        """Return the running operating system to the client
        However, due to security-measures, it will return a standard 'L8' reply

        from the rfc:
            This command is used to find out the type of operating
            system at the server.  The reply shall have as its first
            word one of the system names listed in the current version
            of the Assigned Numbers document [4].
        """
        if not self._isAuthorized(): return
        self.reply(NAME_SYS_TYPE)

    def ftp_ABOR(self, params):
        """This command tells the server to abort the previous FTP
        service command and any associated transfer of data.  The
        abort command may require "special action", as discussed in
        the Section on FTP Commands, to force recognition by the
        server.  No action is to be taken if the previous command
        has been completed (including data transfer).  The control
        connection is not to be closed by the server, but the data
        connection must be closed.

        There are two cases for the server upon receipt of this
        command: (1) the FTP service command was already completed,
        or (2) the FTP service command is still in progress.

           In the first case, the server closes the data connection
           (if it is open) and responds with a 226 reply, indicating
           that the abort command was successfully processed.

           In the second case, the server aborts the FTP service in
           progress and closes the data connection, returning a 426
           reply to indicate that the service request terminated
           abnormally.  The server then sends a 226 reply,
           indicating that the abort command was successfully
           processed.
        """
        if not self._isAuthorized():
            return
        if self.dtp.transport.connected:
            self.dtp.finishGet() # not 100 % perfect on uploads
        self.reply(CLOSING_DATA_CNX)
        
    def lineReceived(self, line):
        "Process the input from the client"
        line = string.strip(line)
        if self.debug:
            log.msg(repr(line))
        command = string.split(line)
        if command == []:
            self.reply(SYNTAX_ERR, '')
            return 0
        commandTmp, command = command[0], ''
        for c in commandTmp:
            if ord(c) < 128:
                command = command + c
        command = string.capitalize(command)
        if self.debug:
            log.msg("-"+command+"-")
        if command == '':
            return 0
        if string.count(line, ' ') > 0:
            params = line[string.find(line, ' ')+1:]
        else:
            params = ''
        # Does this work at all? Quit at ctrl-D
        if ( string.find(line, "\x1A") > -1):
            command = 'Quit'
        method = getattr(self, "ftp_%s" % command, None)
        if method is not None:
            n = method(params)
            if n == 1:
                self.reply(SYNTAX_ERR, string.upper(command))
        else:
            self.reply(SYNTAX_ERR, string.upper(command))

    # TODO: implement ASCII TYPE transfer
    def ftp_TYPE(self, params):
        """ sets data representation type

        from the rfc:

            The argument specifies the representation type as described
            in the Section on Data Representation and Storage.  Several
            types take a second parameter.  The first parameter is
            denoted by a single Telnet character, as is the second
            Format parameter for ASCII and EBCDIC; the second parameter
            for local byte is a decimal integer to indicate Bytesize.
            The parameters are separated by a <SP> (Space, ASCII code
            32).

            The following codes are assigned for type:

                         \    /
               A - ASCII |    | N - Non-print
                         |-><-| T - Telnet format effectors
               E - EBCDIC|    | C - Carriage Control (ASA)
                         /    \
               I - Image
               
               L <byte size> - Local byte Byte size


            The default representation type is ASCII Non-print.  If the
            Format parameter is changed, and later just the first
            argument is changed, Format then returns to the Non-print
            default.
        """
        if not self._isAuthorized(): return
        params = string.upper(params)
        if params in ['A', 'I']:
            self.type = params
            self.reply(TYPE_SET_OK, self.type)
        else:
            return 1

    def ftp_PORT(self, params):
        """Request for an active connection
        This command may be potentially abused, and the only countermeasure
        so far is that no port below 1024 may be targeted.
        An extra approach is to disable port'ing to a third-party ip,
        which is optional through ALLOW_THIRDPARTY.
        Note that this disables 'Cross-ftp' 

        from the rfc:

            The argument is a HOST-PORT specification for the data port
            to be used in data connection.  There are defaults for both
            the user and server data ports, and under normal
            circumstances this command and its reply are not needed.  If
            this command is used, the argument is the concatenation of a
            32-bit internet host address and a 16-bit TCP port address.
            This address information is broken into 8-bit fields and the
            value of each field is transmitted as a decimal number (in
            character string representation).  The fields are separated
            by commas.  A port command would be:

               PORT h1,h2,h3,h4,p1,p2

            where h1 is the high order 8 bits of the internet host
            address.
        """
        if not self._isAuthorized(): return
        params = string.split(params, ',')
        if not (len(params) in [6]): return 1
        peerhost = string.join(params[:4], '.') # extract ip
        peerport = int(params[4])*256+int(params[5])
        # Simple countermeasurements against bouncing
        if peerport < 1024:
            self.reply(CMD_NOT_IMPLMNTD_FOR_PARAM, str(1024))
            return
        if not self.factory.thirdparty:
            sockname = self.transport.getPeer()
            if not (peerhost == sockname[1]):
                self.reply(CMD_NOT_IMPLMNTD_FOR_PARAM, "no third-party transfers")
                return
        self.peerhost = peerhost
        self.peerport = peerport
        self.createActiveServer()
        self.reply(CMD_OK, 'PORT')

    def ftp_PASV(self, params):
        """Request for a passive connection

        from the rfc:
            This command requests the server-DTP to "listen" on a data
            port (which is not its default data port) and to wait for a
            connection rather than initiate one upon receipt of a
            transfer command.  The response to this command includes the
            host and port address this server is listening on.
        """
        if not self._isAuthorized():
            return
        self.createPassiveServer()
        # Use the ip from the pi-connection
        sockname = self.transport.getHost()
        localip = string.replace(sockname[1], '.', ',')
        lport = self.dtpPort.socket.getsockname()[1]

        # what's with the / 256 ?
        lp1 = lport / 256                           
        lp2, lp1 = str(lport - lp1*256), str(lp1)

        # TODO: replace with RESPONSE code
        self.transport.write('227 Entering Passive Mode ('+localip+
                             ','+lp1+','+lp2+')\r\n')

    def ftp_EPSV(self, params):
        "Request for a Extended Passive connection"
        if not self._isAuthorized(): 
            return
        self.createPassiveServer()
        self.reply(ENTERING_EPSV_MODE, `self.dtpPort.socket.getsockname()[1]`)

    def buildFullpath(self, rpath):
        """Build a new path, from a relative path based on the current wd
        This routine is not fully tested, and I fear that it can be
        exploited by building clever paths
        """
        npath = os.path.normpath(rpath)
#        if npath == '':
#            npath = '/'
        if not os.path.isabs(npath):
            npath = os.path.normpath(self.wd + '/' + npath)
        npath = self.root + npath
        return os.path.normpath(npath) # finalize path appending 

# -- TODO: move to FTPFileSystem implementation ----------------------------

    def ftp_PWD(self, params):
        """ Print working directory command
        """
        if not self._isAuthorized(): return
        self.reply(PWD_REPLY, self.wd)

    def ftp_CWD(self, params):
        """Change working directory

        from the rfc:
            This command allows the user to work with a different
            directory or dataset for file storage or retrieval without
            altering his login or accounting information.  Transfer
            parameters are similarly unchanged.  The argument is a
            pathname specifying a directory or other system dependent
            file group designator.
        """
        if not self._isAuthorized(): return
        wd = os.path.normpath(params)
        if not os.path.isabs(wd):
            wd = os.path.normpath(self.wd + '/' + wd)
        wd = string.replace(wd, '\\','/')
        while string.find(wd, '//') > -1:
            wd = string.replace(wd, '//','/')
        # '..', '\\', and '//' is there just to prevent stop hacking :P
        if (not os.path.isdir(self.root + wd)) or (string.find(wd, '..') > 0) or \
            (string.find(wd, '\\') > 0) or (string.find(wd, '//') > 0): 
            self.reply(FILE_NOT_FOUND, params)
            return
        else:
            wd = string.replace(wd, '\\','/')
            self.wd = wd
            self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_CDUP(self, params):
        """Changes to parent directory
        """
        self.ftp_Cwd('..')

    def ftp_SIZE(self, params):
        # is this specified in the RFC?
        """"""
        if not self._isAuthorized(): return
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply(FILE_NOT_FOUND, params)
            return
        self.reply(FILE_STATUS, os.path.getsize(npath))

    def ftp_DELE(self, params):
        """ This command causes the file specified in the pathname to be
        deleted at the server site. 
        """
        if not self._isAuthorized(): return
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply(FILE_NOT_FOUND, params)
            return
        os.remove(npath)
        self.reply(TXFR_COMPLETE_OK)

    def ftp_MKD(self, params):
        """ This command causes the directory specified in the pathname
        to be created as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative).
        """
        if not self._isAuthorized(): return
        npath = self.buildFullpath(params)
        try:
            os.mkdir(npath)
            self.reply(TXFR_COMPLETE_OK)
        except IOError:
            self.reply(FILE_NOT_FOUND)

    def ftp_RMD(self, params):
        """ This command causes the directory specified in the pathname
        to be removed as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative). 
        """
        if not self._isAuthorized(): return
        npath = self.buildFullpath(params)
        if not os.path.isdir(npath):
            self.reply(FILE_NOT_FOUND, params)
            return
        try:
            os.rmdir(npath)
            self.reply(TXFR_COMPLETE_OK)
        except IOError:
            self.reply(FILE_NOT_FOUND)
 
    def ftp_LIST(self, params):
        """ This command causes a list to be sent from the server to the
        passive DTP.  If the pathname specifies a directory or other
        group of files, the server should transfer a list of files
        in the specified directory.  If the pathname specifies a
        file then the server should send current information on the
        file.  A null argument implies the user's current working or
        default directory.
        """
        self.getListing(params)

    def ftp_NLST(self, params):
        """This command causes a directory listing to be sent from
        server to user site.  The pathname should specify a
        directory or other system-specific file group descriptor; a
        null argument implies the current directory. This command is intended
        to return information that can be used by a program to
        further process the files automatically.  For example, in
        the implementation of a "multiple get" function.
        """
        self.getListing(params, 'NLST')

    def getListing(self, params, action='LIST'):
        """generates data for the ftp_List and ftp_Nlist methods
        """
        if not self._isAuthorized():
            return
        if self.dtpPort is None:
            self.reply(CMD_NOT_IMPLMNTD,'LIST')   # and will not be; standard noauth-reply
            return
        if params == "-a": params = '' # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15
        # The reason for this long join, is to exclude access below the root
        npath = self.buildFullpath(params)
        if not os.path.isdir(npath):
            self.reply(FILE_NOT_FOUND, params)
            return
        if not os.access(npath, os.O_RDONLY):
            self.reply(PRMSSN_DENIED, params)
            return
        self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self.queuedfile = npath 
        self.setAction(action)
 
    def ftp_RETR(self, params):
        """ This command causes the server-DTP to transfer a copy of the
        file, specified in the pathname, to the server- or user-DTP
        at the other end of the data connection.  The status and
        contents of the file at the server site shall be unaffected.
        """
        if not self._isAuthorized():
            return
        npath = self.buildFullpath(params)
        if not os.path.isfile(npath):
            self.reply(FILE_NOT_FOUND, params)
            return
        if not os.access(npath, os.O_RDONLY):
            self.reply(PRMSSN_DENIED, params)
            return
        self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self.queuedfile = npath 
        self.setAction('RETR')

    def ftp_STOR(self, params):
        """This command causes the server-DTP to accept the data
        transferred via the data connection and to store the data as
        a file at the server site.  If the file specified in the
        pathname exists at the server site, then its contents shall
        be replaced by the data being transferred.  A new file is
        created at the server site if the file specified in the
        pathname does not already exist.
        """
        if not self._isAuthorized():
            return
        # The reason for this long join, is to exclude access below the root
        npath = self.buildFullpath(params)
        if os.path.isfile(npath):
            # Insert access for overwrite here :)
            #self.reply(FILE_NOT_FOUND, params)
            pass
        self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self.queuedfile = npath 
        self.setAction('STOR')


class IFTPFileSystem(components.Interface):
    """An abstraction of the filesystem commands used by the FTP protocol
    for a given user account
    """
    def pwd(self):
        """ Print working directory command
        """
        pass

    def cwd(self, path):
        """Change working directory

        from the rfc:
            This command allows the user to work with a different
            directory or dataset for file storage or retrieval without
            altering his login or accounting information.  Transfer
            parameters are similarly unchanged.  The argument is a
            pathname specifying a directory or other system dependent
            file group designator.
        """
        pass

    def cdup(self):
        '''changes to the parent of the current working directory
        '''
        pass

    def size(self, path):
        '''returns the size of the file specified by path in bytes
        '''
        pass

    def mkd(self, path):
        """ This command causes the directory specified in the pathname
        to be created as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative).
        """
        pass

    def rmd(self, path):
        """ This command causes the directory specified in the pathname
        to be removed as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative). 
        """
        pass

    def dele(self, path):
        """ This command causes the file specified in the pathname to be
        deleted at the server site. 
        """
        pass

    def list(self, path):
        """ This command causes a list to be sent from the server to the
        passive DTP.  If the pathname specifies a directory or other
        group of files, the server should transfer a list of files
        in the specified directory.  If the pathname specifies a
        file then the server should send current information on the
        file.  A null argument implies the user's current working or
        default directory.
        """
        pass

    def nlst(self, path):
        """This command causes a directory listing to be sent from
        server to user site.  The pathname should specify a
        directory or other system-specific file group descriptor; a
        null argument implies the current directory. This command is intended
        to return information that can be used by a program to
        further process the files automatically.  For example, in
        the implementation of a "multiple get" function.
        """
        pass

    def retr(self, path):
        """ This command causes the server-DTP to transfer a copy of the
        file, specified in the pathname, to the server- or user-DTP
        at the other end of the data connection.  The status and
        contents of the file at the server site shall be unaffected.
        """
        pass

    def stor(self, params):
        """This command causes the server-DTP to accept the data
        transferred via the data connection and to store the data as
        a file at the server site.  If the file specified in the
        pathname exists at the server site, then its contents shall
        be replaced by the data being transferred.  A new file is
        created at the server site if the file specified in the
        pathname does not already exist.
        """
        pass
 







