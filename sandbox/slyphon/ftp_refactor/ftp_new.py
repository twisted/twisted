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

"""
An FTP protocol implementation

Maintainer: U{Jonathan D. Simms<mailto:slyphon@twistedmatrix.com>}

"""

# System Imports
import os
import time
import string
import types
import re
from cStringIO import StringIO
from math import floor

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error, defer
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic, policies
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter

from twisted import application, internet, python
from twisted.python import failure, log, components

from twisted.cred import error as cred_error, portal, checkers, credentials



ENDLN = str('\015\012')

# response codes

RESTART_MARKER_REPLY                    = "100"
SERVICE_READY_IN_N_MINUTES              = "120"
DATA_CNX_ALREADY_OPEN_START_XFR         = "125"
FILE_STATUS_OK_OPEN_DATA_CNX            = "150"

CMD_OK                                  = "200.1"
TYPE_SET_OK                             = "200.2"
ENTERING_PORT_MODE                      = "200.3"
CMD_NOT_IMPLMNTD_SUPERFLUOUS            = "202"
SYS_STATUS_OR_HELP_REPLY                = "211.1"
FEAT_REPLY                              = "211.2"
DIR_STATUS                              = "212"
FILE_STATUS                             = "213"
HELP_MSG                                = "214"
NAME_SYS_TYPE                           = "215"
SVC_READY_FOR_NEW_USER                  = "220.1"
WELCOME_MSG                             = "220.2"
SVC_CLOSING_CTRL_CNX                    = "221"
GOODBYE_MSG                             = "221"
DATA_CNX_OPEN_NO_XFR_IN_PROGRESS        = "225"
CLOSING_DATA_CNX                        = "226"
TXFR_COMPLETE_OK                        = "226"
ENTERING_PASV_MODE                      = "227"
ENTERING_EPSV_MODE                      = "229"
USR_LOGGED_IN_PROCEED                   = "230.1"     # v1 of code 230
GUEST_LOGGED_IN_PROCEED                 = "230.2"     # v2 of code 230
REQ_FILE_ACTN_COMPLETED_OK              = "250"
PWD_REPLY                               = "257"

USR_NAME_OK_NEED_PASS                   = "331.1"     # v1 of Code 331
GUEST_NAME_OK_NEED_EMAIL                = "331.2"     # v2 of code 331
NEED_ACCT_FOR_LOGIN                     = "332"
REQ_FILE_ACTN_PENDING_FURTHER_INFO      = "350"

SVC_NOT_AVAIL_CLOSING_CTRL_CNX          = "421.1"
TOO_MANY_CONNECTIONS                    = "421.2"
CANT_OPEN_DATA_CNX                      = "425"
CNX_CLOSED_TXFR_ABORTED                 = "426"
REQ_ACTN_ABRTD_FILE_UNAVAIL             = "450"
REQ_ACTN_ABRTD_LOCAL_ERR                = "451"
REQ_ACTN_ABRTD_INSUFF_STORAGE           = "452"

SYNTAX_ERR                              = "500"
SYNTAX_ERR_IN_ARGS                      = "501"
CMD_NOT_IMPLMNTD                        = "502"
BAD_CMD_SEQ                             = "503"
CMD_NOT_IMPLMNTD_FOR_PARAM              = "504"
NOT_LOGGED_IN                           = "530.1"     # v1 of code 530 - please log in
AUTH_FAILURE                            = "530.2"     # v2 of code 530 - authorization failure
NEED_ACCT_FOR_STOR                      = "532"
FILE_NOT_FOUND                          = "550.1"     # no such file or directory
PERMISSION_DENIED                       = "550.2"     # permission denied
ANON_USER_DENIED                        = "550.3"     # anonymous users can't alter filesystem
IS_NOT_A_DIR                            = "550.4"     # rmd called on a path that is not a directory
REQ_ACTN_NOT_TAKEN                      = "550.5"
PAGE_TYPE_UNK                           = "551"
EXCEEDED_STORAGE_ALLOC                  = "552"
FILENAME_NOT_ALLOWED                    = "553"


RESPONSE = {
    # -- 100's --
    RESTART_MARKER_REPLY:               '110 MARK yyyy-mmmm', # TODO: this must be fixed
    SERVICE_READY_IN_N_MINUTES:         '120 service ready in %s minutes',
    DATA_CNX_ALREADY_OPEN_START_XFR:    '125 Data connection already open, starting transfer',
    FILE_STATUS_OK_OPEN_DATA_CNX:       '150 File status okay; about to open data connection.',

    # -- 200's --
    CMD_OK:                             '200 Command OK',
    TYPE_SET_OK:                        '200 Type set to %s.',
    ENTERING_PORT_MODE:                 '200 PORT OK',
    CMD_NOT_IMPLMNTD_SUPERFLUOUS:       '202 command not implemented, superfluous at this site',
    SYS_STATUS_OR_HELP_REPLY:           '211 system status reply',
    FEAT_REPLY:                         '211-system extensions\r\n \r\n211 end',
    DIR_STATUS:                         '212 %s',
    FILE_STATUS:                        '213 %s',
    HELP_MSG:                           '214 help: %s',
    NAME_SYS_TYPE:                      '215 UNIX Type: L8',
    WELCOME_MSG:                        "220-Welcome, ask your doctor if twistedmatrix.com is right for you!\r\n220 Features p .",
    SVC_READY_FOR_NEW_USER:             '220 Service ready',
    GOODBYE_MSG:                        '221 Goodbye.',
    DATA_CNX_OPEN_NO_XFR_IN_PROGRESS:   '225 data connection open, no transfer in progress',
    CLOSING_DATA_CNX:                   '226 Abort successful',
    TXFR_COMPLETE_OK:                   '226 Transfer Complete.',
    ENTERING_PASV_MODE:                 '227 =%s',
    ENTERING_EPSV_MODE:                 '229 Entering Extended Passive Mode (|||%s|).', # where is epsv defined in the rfc's?
    USR_LOGGED_IN_PROCEED:              '230 User logged in, proceed',
    GUEST_LOGGED_IN_PROCEED:            '230 Anonymous login ok, access restrictions apply.',
    REQ_FILE_ACTN_COMPLETED_OK:         '250 Requested File Action Completed OK', #i.e. CWD completed ok
    PWD_REPLY:                          '257 "%s" is current directory.',

    # -- 300's --
    'userotp':                          '331 Response to %s.',  # ???
    USR_NAME_OK_NEED_PASS:              '331 Password required for %s.',
    GUEST_NAME_OK_NEED_EMAIL:           '331 Guest login ok, type your email address as password.',

    # -- 400's --
    SVC_NOT_AVAIL_CLOSING_CTRL_CNX:     '421 Service not available, closing control connection.',
    TOO_MANY_CONNECTIONS:               '421 Too many users right now, try again in a few minutes.',
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
    NEED_ACCT_FOR_STOR:                 '532 Need an account for storing files',
    FILE_NOT_FOUND:                     '550 %s: No such file or directory.',
    PERMISSION_DENIED:                  '550 %s: Permission denied.',
    ANON_USER_DENIED:                   '550 Anonymous users are forbidden to change the filesystem', 
    IS_NOT_A_DIR:                       '550 cannot rmd, %s is not a directory',
    REQ_ACTN_NOT_TAKEN:                 '550 requested action not taken: %s',
    EXCEEDED_STORAGE_ALLOC:             '552 requested file action aborted, exceeded file storage allocation',
    FILENAME_NOT_ALLOWED:               '553 requested action not taken, file name not allowed'
}

   
        
# -- Custom Exceptions --
class TLDNotSetInRealmError(Exception):
    '''raised if the tld (root) directory for the Realm was not set 
    before requestAvatar was called'''
    pass

class FileNotFoundError(Exception):
    pass

class PermissionDeniedError(Exception):
    pass

class AnonUserDeniedError(Exception):
    """raised when an anonymous user issues a command
    that will alter the filesystem
    """
    pass

class IsNotADirectoryError(Exception):
    """raised when RMD is called on a path that isn't a directory
    """
    pass

class OperationFailedError(Exception):
    """raised when a command like rmd or mkdir fails for a reason other than permissions errors
    """
    pass

class CmdSyntaxError(Exception):
    pass

class CmdArgSyntaxError(Exception):
    pass

class CmdNotImplementedError(Exception):
    """raised when an unimplemented command is given to the server
    """
    pass

class CmdNotImplementedForArgError(Exception):
    pass

class FTPError(Exception):
    pass

class FTPTimeoutError(Exception):
    pass

class DTPError(Exception):
    pass

class BogusClientError(Exception):
    """thrown when a client other than the one we opened this 
    DTP connection for attempts to connect, or a client attempts to
    get us to connect to an ip that differs from the one where the 
    request came from"""
    pass

class PathBelowTLDError(Exception):
    pass

class ClientDisconnectError(Exception):
    pass

class BadCmdSequenceError(Exception):
    """raised when a client sends a series of commands in an illogical sequence"""
    pass

class AuthorizationError(Exception):
    """raised when client authentication fails"""
    pass



# --- DTP Protocol ---------------------------------------------------------

class DTPFileSender(basic.FileSender):
    def resumeProducing(self):
        chunk = ''
        if self.file:
            chunk = self.file.read(self.CHUNK_SIZE)
        if not chunk:
            self.file = None
            self.consumer.unregisterProducer()
            log.debug("producer has unregistered?: %s" % (self.consumer.producer is None))
            if self.deferred:
                self.deferred.callback(self.lastSent)
                self.deferred = None
            return
        
        if self.transform:
            chunk = self.transform(chunk)
        self.consumer.write(chunk)
        self.lastSent = chunk[-1]

    def stopProducing(self):
        if self.deferred:
            self.deferred.errback(ClientDisconnectError())
            self.deferred = None

# -- Utility Functions --

def debugDeferred(self, *_):
    log.debug('debugDeferred(): %s' % str(_))
 
def _getFPName(fp):
    """returns a file object's name attr if it has one,
    otherwise it returns "<string>"
    """
    if hasattr(fp, 'name'):
        return fp.name
    # stringIO objects have no .name attr
    return getattr(fp, 'name', '<string>')

class IDTPParent(object):
    """An interface for protocols that wish to use a DTP sub-protocol and
    factory. 

    @ivar dtpFactory: the dtp factory that creates an instance when needed
    @ivar dtpInstance: the instance that the factory creates. since only
        one dtp instance is created, this will be a single object reference
    @ivar dtpTxfrMode: binary or ascii, right now dtp ignores this and only
        does binary transfers
    @ivar dtpPort: value returned from listenTCP or connectTCP
    @ivar peerHost: the (type,ip,port) of the other server
    """
    def finishedFileTransfer(self):
        """performs cleanup on the dtpInstance once the transfer is complete"""
        pass

class IDTPFactory(object):
    """An interface for protocol.Factories 

    @ivar peerCheck: perform checks to make sure the ftp-pi's peer is the same
        as the dtp's
    @ivar pi: a reference to this factory's protocol interpreter
    """
    def __init__(self, pi, peerHost=None):
        """Constructor
        @param pi: this factory's protocol interpreter
        @param peerHost: if peerCheck is True, this is the tuple that the
            generated instance will use to perform security checks
        """
        pass

class DTP(object, protocol.Protocol):
    """The Data Transfer Protocol for this FTP-PI instance
    all dtp_* methods return a deferred
    """
    isConnected = False 
    reTransform = re.compile(r'(?<!\r)\n') # says, match an \n that's not immediately preceeded by a \r

    def connectionMade(self):
        """Will start an transfer, if one is queued up, 
        when the client connects"""
        self.factory.dtpTimeout.cancel()
        self.factory.setTimeout(None)
        peer = self.transport.getPeer()
        self.isConnected = True

        if peer[1] != self.factory.peerHost[1]:
            # DANGER Will Robinson! Bailing!
            log.debug('dtp ip did not match ftp ip')
            d.errback(BogusClientError("%s != %s" % (peer[1], self.factory.peerHost[1])))   
            return

        log.msg('calling self.factory._unblock()')
        self.factory._unblock()

    def connectionLost(self, reason):
        log.debug('dtp.connectionLost: %s' % reason)
        self.factory.finishedFileTransfer()
        self.isConnected = False

    def transformChunk(self, chunk):
        log.msg('transformChunk: before = %s' % chunk)
        newChunk = self.reTransform.sub('\r\n', chunk)
        log.msg('transformChunk: after = %s' % newChunk)
        return newChunk

    def dtp_RETR(self): # RETR = sendFile
        """ssnds a file object out the wire
        @param fpSizeTuple a tuple of a file object and that file's size
        """
        filename = _getFPName(self.factory.fp)

        log.debug('sendfile sending %s' % filename)

        fs = DTPFileSender()
        if self.factory.binary:
            transform = None
        else:
            transform = self.transformChunk
        
        # lets set self.factory.fp file pointer to 0 just to 
        # make sure the avatar didn't forget, hmm?
        self.factory.fp.seek(0)
        
        return fs.beginFileTransfer(self.factory.fp, self.transport, transform
                ).addCallback(self._dtpPostTransferCleanup
                )

    def _dtpPostTransferCleanup(self, *arg):
        log.debug("dtp._dtpPostTransferCleanup")
        self.transport.loseConnection()
        self.factory.cleanupDTP()


# ----------------------------------------------------------------------------

class FTP(object, basic.LineReceiver, policies.TimeoutMixin, protocol.Factory):      
    """Protocol Interpreter for the File Transfer Protocol
    
    @ivar shell: The connected avatar
    @ivar user: The username of the connected client
    @ivar peerHost: The (type, ip, port) of the client
    @ivar dtpPortMode: The current mode -- PASV or PORT
    @ivar blocked: Command queue for command pipelining
    @ivar binary: The transfer mode.  If false, ASCII.
    @ivar dtpPort: Port returned from listenTCP
    @ivar dtpInetPort: dtpPort.getHost()
    @ivar dtpHostPort: cluient (address, port) to connect to on a PORT command
    """
    __implements__ = IProtocol,
    # FTP is a bit of a misonmer, as this is the PI - Protocol Interpreter
    blockingCommands = ['RETR', 'STOR', 'LIST', 'PORT']
    reTelnetChars = re.compile(r'(\\x[0-9a-f]{2}){1,}')


    # if this instance is the upper limit of instances allowed, then 
    # reply with appropriate error message and drop the connection
    _instanceNum = 0

    portal      = None

    # the avatar
    shell       = None     

    # the username of the client connected
    user        = None     

    # the (type,ip,port) of the client
    peerHost    = None     

    # a command queue for pipelining
    blocked     = None     

    # defaults to PORT
    dtpPortMode = None     

    # a DTP protocol instance
    dtpInstance = None     

    # object returned from listenTCP
    dtpPort     = None     

    # returned from reactor.callLater, times out dtp if no
    # one connects in self.factory.dtpTimeoutTime seconds
    dtpTimeout = None

    # result of dtpPort.getHost() used for saving inet port number
    dtpInetPort = None     

    # client address/port to connect to on PORT command
    dtpHostPort = None     

    # deferred that's fired on dtp connectionMade 
    dtpConnected = defer.Deferred()
    
    # binary transfers? only support binary for now
    binary = True     

    # either 'ftp' or 'dtp' depending what state the protocol is in
    state = "ftp"    

    # the file object to transfer via dtp
    fp = None

    def connectionMade(self):
        log.debug('ftp-pi connectionMade: instance %s' % self._instanceNum)

        if (self.factory._maxProtocolInstances is not None and 
                self._instanceNum >= self.factory._maxProtocolInstances): 
            self.reply(TOO_MANY_CONNECTIONS)
            self.transport.loseConnection()
            return
        self.reply(WELCOME_MSG)                     
        self.peerHost = self.transport.getPeer()
        self.setTimeout(self.timeOut)

    def connectionLost(self, reason):
        log.msg("Oops! lost connection\n %s" % reason)
        # if we have a DTP protocol instance running and
        # we lose connection to the client's PI, kill the 
        # DTP connection and close the port
        if self.dtpInstance:
            self.cleanupDTP()
        self.setTimeout(None) 
        self.factory._currentInstanceNum -= 1
        # moshez crackful optimization
        # checks for self.shell.logout and if it exists
        # calls it
#        getattr(self.shell, 'logout', lambda: None)()
        return

    def timeoutConnection(self):
        log.msg('FTP timed out')
        self.transport.loseConnection()

    def setTimeout(self, seconds):
#        log.msg("FTP set timeout to %s" % seconds)
        policies.TimeoutMixin.setTimeout(self, seconds)

    def reply(self, key, s=''):                                               
        """format a RESPONSE and send it out over the wire"""
        if string.find(RESPONSE[key], '%s') > -1:
            self.transport.write(RESPONSE[key] % s + ENDLN)
        else:
            self.transport.write(RESPONSE[key] + ENDLN)

    def lineReceived(self, line):
        "Process the input from the client"
        self.resetTimeout()
        line = string.strip(line)
        line = self.reTelnetChars.sub('', line)  # clean up '\xff\xf4\xff' nonsense
        try:
            line = line.encode() 
        except TypeError, e:
            reply(SYNTAX_ERR)
            return

        # TODO: need to simplify this...badly

        try:
            cmdAndArgs = line.split(' ',1)
            self.processCommand(*cmdAndArgs)
        except CmdSyntaxError, (e,):
            self.reply(SYNTAX_ERR, string.upper(command))
        except CmdArgSyntaxError, (e,):
#            log.debug(e)
            self.reply(SYNTAX_ERR_IN_ARGS, e)
        except AnonUserDeniedError, (e,):
#            log.debug(e)
            self.reply(ANON_USER_DENIED, e)
        except CmdNotImplementedError, (e,):
#            log.debug(e)
            self.reply(CMD_NOT_IMPLMNTD, e)
        except BadCmdSequenceError, (e,): 
#            log.debug(e)
            self.reply(BAD_CMD_SEQ, e)
        except AuthorizationError, (e,):
#            log.debug(e)
            self.reply(AUTH_FAILURE, 'internal server error')
        except FileNotFoundError, (e,):
#            log.debug(e)
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, (e,):
#            log.debug(e)
            self.reply(PERMISSION_DENIED, e)
        except OperationFailedError, (e,):
#            log.debug(e)
            self.reply(REQ_ACTN_NOT_TAKEN, '')
        except Exception, e:
            log.err(e)
            self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')
            raise

    def processCommand(self, cmd, *args):
        # all DTP commands block, so queue new requests
        if self.blocked != None:
            self.blocked.append((cmd,args))
            return

        cmd = cmd.upper()
        # these are the only two commands that don't require
        # an authenticated user
        if cmd not in ['USER','PASS'] and not self.shell:                       
            log.debug('ftp_%s returning, user not logged in' % cmd)             
            self.reply(NOT_LOGGED_IN)
            return

        if cmd in self.blockingCommands:                                        # if this is a DTP related command
            if not self.dtpInstance:                                            # if no one has connected yet
                # a bit hackish, but manually blocks this command 
                # until we've set up the DTP protocol instance
                # _unblock will run this first command and subsequent
                self.blocked = [(cmd,args)]                                     # add item to queue and start blocking
                return
                                              
        try:
            getattr(self, "ftp_%s" % cmd)(*args)
        except AttributeError, e:
            raise CmdNotImplementedError(cmd)                 # if we didn't find cmd, raise an error and alert client

    def _unblock(self, *_):
        commands, self.blocked = self.blocked, None
        while commands:
            # while no other method has set self.blocked
            # pop a command off the queue and process it
            if self.blocked is None:                         
                cmd, args = commands.pop(0)                  
                self.processCommand(cmd, *args)              

            # if someone has blocked during the time we were processing
            # add our commands that we dequeued back into the queue
            else:                                            
                self.blocked.extend(commands)                

    def _createDTP(self):
        self.setTimeout(None)
        if self.dtpInstance is None:
            if self.dtpPortMode:
                # XXX: this doesn't work for right now
                self.dtpPort = reactor.connectTCP(self.dtpHostPort[1], self.dtpHostPort[2]) 
            else:
                self.dtpPort = reactor.listenTCP(0, self)    
                def _timeout():
                    if self.dtpPort:
                        self.dtpPort.stopListening()
                self.dtpTimeout = reactor.callLater(self.factory.dtpTimeoutTime, _timeout)

    # ---------------------------------------------------------------
    # The PI is also a dtp factory, as there's a 1:1 relationship
    # this makes it easier, because the dtp.factory points to this object

    def buildProtocol(self, addr):
#        log.debug('buildProtocol')
        if self.dtpInstance:   # only create one instance
            return 
        p = DTP()
        p.factory = self
        self.dtpInstance = p
        return p

    # ---------------------------------------------------------------

    def cleanupDTP(self):
        """call when DTP connection exits
        """
        dtpPort, self.dtpPort = self.dtpPort, None
        dtpPort.stopListening()
        self.dtpInstance = None
        self.resetTimeout()
        self.finishedFileTransfer()
        self._unblock()


    def _doDTPCommand(self, cmd, *arg): 
        self.setTimeout(None)               # don't Time out when waiting for DTP Connection
        log.debug('FTP._doDTPCommand: self.blocked: %s' % self.blocked)
        if self.blocked is None:
            self.blocked = []
        try:
            f = getattr(self.dtpInstance, "dtp_%s" % cmd, None)
#            log.debug('running dtp function %s' % f)
        except AttributeError, e:
            log.err('SOMETHING IS SCREWY IN _doDTPCommand')
            raise e
        else:
#            self.dtpFactory.setTimeout(self.dtpTimeout)
            if arg:
                d = f(arg)
            else:
                d = f()

            def cb(_):
                """called back when any DTP command has completed successfully"""
                log.debug("DTP Command success")

            def eb(error):
                log.msg(error)
                self.setTimeout(self.factory.timeOut)       # restart timeOut clock after DTP returns
                r = error.trap(defer.TimeoutError,          # this is called when DTP times out
                               BogusClientError,            # called if PI & DTP clients don't match
                               FTPTimeoutError,             # called when FTP connection times out
                               ClientDisconnectError)       # called if client disconnects prematurely during DTP transfer
                               
                if r == defer.TimeoutError:                     
                    self.reply(CANT_OPEN_DATA_CNX)
                elif r in (BogusClientError, FTPTimeoutError):
                    self.reply(SVC_NOT_AVAIL_CLOSING_CTRL_CNX)
                    self.transport.loseConnection()
                elif r == ClientDisconnectError:
                    self.reply(CNX_CLOSED_TXFR_ABORTED)

                # if we timeout, or if an error occurs, 
                # all previous commands are junked
                self.blocked = None 

        d.addCallback(cb).addErrback(eb)


    def finishedFileTransfer(self, *arg):
        """called back when a file transfer has been completed by the dtp"""
#        log.debug('finishedFileTransfer! cleaning up DTP')
        if self.fp != None and not self.fp.closed:
            if self.fp.tell() == self.fpsize:
                log.debug('transfer completed okay :-)')
                self.reply(TXFR_COMPLETE_OK)
            else:
                log.debug("uh-oh there was an error...must have been the client's fault")
                self.reply(CNX_CLOSED_TXFR_ABORTED)
            self.fp.close()

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
            raise CmdSyntaxError('no parameters')
        self.user = string.split(params)[0]
#        log.debug('ftp_USER params: %s' % params)
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)

    # TODO: add max auth try before timeout from ip...

    def ftp_PASS(self, params=''):
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
            raise BadCmdSequenceError('USER required before PASS')

        if params == '':
            raise CmdArgSyntaxError('you must specify a password with PASS')
        
        self.passwd = params.split()[0]        # parse password 

        # if this is an anonymous login
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.passwd = params
            if self.portal:
                self.portal.login(
                        credentials.Anonymous(), 
                        None, 
                        IShell
                    ).addCallbacks(self._cbAnonLogin, self._ebLogin
                    )
            else:
                # if cred has been set up correctly, this shouldn't happen
                raise AuthorizationError('internal server error')

        # otherwise this is a user login
        else:
            if self.portal:
                self.portal.login(
                        credentials.UsernamePassword(self.user, self.passwd),
                        None,
                        IShell
                    ).addCallbacks(self._cbLogin, self._ebLogin
                    )
            else:
                raise AuthorizationError('internal server error')

    def _cbAnonLogin(self, (interface, avatar, logout)):
        """sets up anonymous login avatar"""
#        assert interface is IShell
        if interface is not IShell:
            raise NotImplementedError('interface must be or derive from ftp.IShell')

        peer = self.transport.getPeer()
#       log.debug("Anonymous login from %s:%s" % (peer[1], peer[2]))
        self.shell = avatar
        # XXX: Check to see if this is correct:
        #      should logout be assigned to avatar?
        self.shell.logout = logout
        self.reply(GUEST_LOGGED_IN_PROCEED)

    def _cbLogin(self, (interface, avatar, logout)):
        """sets up authorized user login avatar"""
        # XXX: How handle this exception?
        if interface is not IShell:
            raise NotImplementedError('interface must be or derive from ftp.IShell')
        self.shell = avatar
        self.logout = logout
        self.reply(USR_LOGGED_IN_PROCEED)

    def _ebLogin(self, failure):
        r = failure.trap(cred_error.UnauthorizedLogin, TLDNotSetInRealmError)
        if r == TLDNotSetInRealmError:
            log.debug(failure.getErrorMessage())
            self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')
            self.transport.loseConnection()
        else:
            self.reply(AUTH_FAILURE, '')

    def ftp_TYPE(self, params):
        p = params[0].upper()
        if p[0] not in ['I', 'A', 'L']:
            raise CmdArgSyntaxError(p[0])
        elif p[0] in ['I', 'L']:
            self.binary = True
            self.reply(TYPE_SET_OK, p)
        elif p[0] == 'A':
            self.binary = False
            self.reply(TYPE_SET_OK, p)
        else:
            raise CmdSyntaxError(p)

    def ftp_SYST(self, params=None):
        self.reply(NAME_SYS_TYPE)

    def ftp_LIST(self, params=''):
        """ This command causes a list to be sent from the server to the
        passive DTP.  If the pathname specifies a directory or other
        group of files, the server should transfer a list of files
        in the specified directory.  If the pathname specifies a
        file then the server should send current information on the
        file.  A null argument implies the user's current working or
        default directory.
        """
#        log.debug('ftp_LIST: %s' % params)
        if params == "-a": params = ''  # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15

        self.fp, self.fpsize = self.shell.list(cleanPath(params))    # returns a StringIO object
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR')

    def ftp_SIZE(self, params=''):
#        log.debug('ftp_SIZE: %s' % params)
        filesize = self.shell.size(cleanPath(params))
        self.reply(FILE_STATUS, filesize)

    def ftp_MDTM(self, params=''):
#        log.debug('ftp_MDTM: %s' % params)
        dtm = self.shell.mdtm(cleanPath(params))
        self.reply(FILE_STATUS, dtm)
 
    def ftp_PWD(self, params=''):
        """ Print working directory command
        """
        self.reply(PWD_REPLY, self.shell.pwd())

    def ftp_PASV(self):
        """Request for a passive connection

        reply is in format 227 =h1,h2,h3,h4,p1,p2

        from the rfc:
            This command requests the server-DTP to "listen" on a data
            port (which is not its default data port) and to wait for a
            connection rather than initiate one upon receipt of a
            transfer command.  The response to this command includes the
            host and port address this server is listening on.
        """
        # NOTE: Normally, the way DTP related commands work is that they
        # go through the PI processing (what goes on here), and then make
        # the appropriate call to _doDTPCommand. 
        # 
        # however, in this situation, since this is likely the first command
        # that will be run that has to do with the DTP factory, we
        # call _createDTP explicitly (as opposed to letting _doDTPCommand
        # do it for us).
        #
        # summary: this method is a special case, so keep that in mind
        #
        self.dtpPortMode = False

        # XXX: change as appropriate to refactoring

        if self.dtpInstance:                 # if we have a DTP port set up
            self.cleanupDTP()               # lose it 
        if not self.dtpInstance:             # if we haven't set up a DTP port yet (or just closed one)
            try:
                self._createDTP()
            except OSError, (e,):           # we're watching for a could not listen on port error
                log.msg("CRITICAL BUG!! THIS SHOULD NOT HAVE HAPPENED!!! %s" % e)
        sockname = self.transport.getHost()                # Use the ip from the PI-connection
        localip = string.replace(sockname[1], '.', ',')    # format the reply 
        lport = self.dtpPort.socket.getsockname()[1]
        lp1 = lport / 256                                  # convert port into two 8-byte values
        lp2, lp1 = str(lport - lp1*256), str(lp1)
        self.reply(ENTERING_PASV_MODE, "%s,%s,%s" % (localip, lp1, lp2))
        log.debug("passive port open on: %s:%s" % (localip, lport), level="debug")

    def decodeHostPort(self, line):
        """Decode an FTP response specifying a host and port.
        
        see RFC sec. 4.1.2 "PASV"

        @returns: a 2-tuple of (host, port).
        """
        #abcdef = re.sub('[^0-9, ]', '', line[4:])
        abcdef = re.sub('[^0-9, ]', '', line)
        a, b, c, d, e, f = map(str.strip, abcdef.split(','))
        host = "%s.%s.%s.%s" % (a, b, c, d)
        port = (int(e)<<8) + int(f)
        return (host, port)

    def ftp_PORT(self, params):

        # XXX: change as appropriate to refactoring

        self.dtpPortMode = True 
        self.dtpHostPort = self.decodeHostPort(params)
        if self.dtpInstance:                 # if we have a DTP port set up
            self.cleanupDTP()               # lose it 
        if not self.dtpInstance:             # if we haven't set up a DTP port yet (or just closed one)
            try:
                self._createDTP()
            except OSError, (e,):           # we're watching for a could not listen on port error
                log.msg("CRITICAL BUG!! THIS SHOULD NOT HAVE HAPPENED!!! %s" % e)
        self.reply(PORT_MODE_OK)

    def ftp_CWD(self, params):
        self.shell.cwd(cleanPath(params))
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_CDUP(self):
        self.shell.cdup()
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_RETR(self, params):

        if self.dtpPortMode is None:
            raise BadCmdSequenceError('must send PORT or PASV before RETR')
        self.fp, self.fpsize = self.shell.retr(cleanPath(params))
        #log.debug('self.fp = %s, self.fpsize = %s' % (self.fp, self.fpsize))
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR')

    def ftp_STRU(self, params=""):
        p = params.upper()
        if params == 'F': return self.reply(CMD_OK)
        raise CmdNotImplementedForArgError(params)

    def ftp_MODE(self, params=""):
        p = params.upper()
        if params == 'S': return self.reply(CMD_OK)
        raise CmdNotImplementedForArgError(params)

    def ftp_QUIT(self, params=''):
        self.transport.loseConnection()
        log.debug("Client Quit")

    def ftp_FEAT(self, params=''):
        # an extention in RFC 2389 that ncftp _insists_ on using
        self.reply(FEAT_REPLY)

    def ftp_HELP(self, params=''):
        # I don't know nothin'
        self.reply(SYNTAX_ERR)

    def ftp_CLNT(self, params=''):
        # another dumb thing that ncftp wants a response to
        self.reply(SYNTAX_ERR)

class Factory(protocol.Factory):
    """A factory for producing ftp protocol instances
    @ivar maxProtocolInstances: the maximum number of FTP protocol instances
        this factory will create. When the maximum number is reached, a protocol
        instance will be spawned that will give the "Too many connections" message
        to the client and then close the connection.
        Set to None for unlimited connections
    @ivar timeOut: the protocol's idle timeout time in seconds, default is 600 seconds
    """
    protocol = FTP
    allowAnonymous = True
    userAnonymous = None
    timeOut = 600
    dtpTimeoutTime = 30.0

    _maxProtocolInstances = None
    _currentInstanceNum = 0
    _instances = []

    # if no anonymousUserName is specified, 
    # no anonymous logins allowed
    def __init__(self, portal=None, #anonymousUserName=None, 
                       maxProtocolInstances=None):
        self.portal = portal
#        self.userAnonymous = anonymousUserName
#        if anonymousUserName is None:
#            self.allowAnonymous = False
        self._maxProtocolInstances = maxProtocolInstances
        reactor._pi = self

    def buildProtocol(self, addr):
        log.debug('%s of %s max ftp instances: ' % (self._currentInstanceNum, self._maxProtocolInstances))
        pi            = protocol.Factory.buildProtocol(self, addr)
        pi.protocol   = self.protocol
        pi.portal     = self.portal
        pi.factory    = self
        if self._maxProtocolInstances is not None:
            self._currentInstanceNum += 1
            pi._instanceNum = self._currentInstanceNum
        self._instances.append(pi)
        return pi

    def stopFactory(self):
        # make sure ftp instance's timeouts are set to None
        # to avoid reactor complaints
        [p.setTimeout(None) for p in self._instances if p.timeOut is not None]

FTPFactory = Factory
        
# -- Cred Objects --

class IShell(components.Interface):
    """An abstraction of the shell commands used by the FTP protocol
    for a given user account
    """

    def mapCPathToSPath(self, path):
        """converts a specified path relative to the user's top level directory
        into a path in the filesystem representation

        example: if the user's tld is /home/foo and there's a file in the filesystem
        /home/foo/bar/spam.tar.gz the user would specify path /bar/spam.tar.gz in the 
        ftp command, and this function would translate it into /home/foo/bar/spam.tar.gz

        @returns a tuple (cpath, spath) where cpath is the client's top level directory
        plus path, and spath is cpath in relation to the server's filesystem.

        cpath is an illusion, spath is a real file in the filesystem
        """
        pass

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

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def cdup(self):
        """changes to the parent of the current working directory
        """
        pass

    def size(self, path):
        """returns the size of the file specified by path in bytes
        """
        pass

    def mkd(self, path):
        """ This command causes the directory specified in the pathname
        to be created as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative).

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def rmd(self, path):
        """ This command causes the directory specified in the pathname
        to be removed as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative). 

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def dele(self, path):
        """This command causes the file specified in the pathname to be
        deleted at the server site. 

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def list(self, path):
        """@return: a tuple of (StringIO_object, size) containing the directory 
        listing to be sent to the client via the DTP
        

        from the rfc:
            This command causes a list to be sent from the server to the
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

        @param path: the path to generate output for
        @type path: string
        """
        pass

    def retr(self, path):
        """ This command causes the server-DTP to transfer a copy of the
        file, specified in the pathname, to the server- or user-DTP
        at the other end of the data connection.  The status and
        contents of the file at the server site shall be unaffected.

        @return: a tuple of (fp, size) where fp is an opened file-like object 
        to the data requested and size is the size, in bytes, of fp
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

    def mdtm(self, path):
        """get the date and time for path
        @param path: the path you're interested in
        @type path: string
        @return: the date of path in the form of %Y%m%d%H%M%S
        @rtype: string
        """
        pass


try:
    import pwd, grp
except ImportError:
    print "sorry, currently ftpdav only works with linux and linux variants"
    raise SystemExit("ftp cred doesn't do windows")

def _callWithDefault(default, _f, *_a, **_kw):
    try:
        return _f(*_a, **_kw)
    except KeyError:
        return default

def _memberGIDs(gid):
    """returns a list of all gid's that are a member of group with id
    """
    gr_mem = 3
    return grp.getgrgid(gid)[gr_mem]

def _testPermissions(uid, gid, spath, mode='r'):
    """checks to see if uid has proper permissions to access path with mode
    @param uid: numeric user id
    @type uid: int
    @param gid: numeric group id
    @type gid: int
    @param spath: the path on the server to test
    @type spath: string
    @param mode: 'r' or 'w' (read or write)
    @type mode: string
    @returns: a True if the uid can access path
    @rval: Boolean
    """
    import os.path as osp 
    import stat
    if mode not in ['r', 'w']:
        raise ValueError("mode argument must be 'r' or 'w'")
    
    readMasks = {'usr': stat.S_IRUSR, 'grp': stat.S_IRGRP, 'oth': stat.S_IROTH}
    writeMasks = {'usr': stat.S_IWUSR, 'grp': stat.S_IWGRP, 'oth': stat.S_IWOTH}
    modes = {'r': readMasks, 'w': writeMasks}
    log.msg('running _testPermissions')
    if osp.exists(spath):
        s = os.lstat(spath)
        if uid == 0:    # root is superman, can access everything
            log.msg('uid == root, can do anything!')
            return True
        elif modes[mode]['usr'] & s.st_mode > 0 and uid == s.st_uid:
            log.msg('usr has proper permissions')
            return True
        elif ((modes[mode]['grp'] & s.st_mode > 0) and 
                (gid == s.st_gid or gid in _memberGIDs(gid))):
            log.msg('grp has proper permissions')
            return True
        elif modes[mode]['oth'] & s.st_mode > 0:
            log.msg('oth has proper permissions')
            return True
    return False   


def cleanPath(path):
    # cleanup backslashes and multiple foreslashes
#    log.debug("pre-cleaned path: %s" % path)
    if path:
        path = re.sub(r'[\\]{2,}?', '/', path)
        path = re.sub(r'[/]{2,}?','/', path)
        path = re.sub(r'[*]?', '', path)
    path = os.path.normpath(path)
#    log.debug('cleaned path: %s' % path)
    return path

class AnonymousShell(object):
    """Only works on POSIX platforms at the moment."""
    __implements__ = IShell

    uid      = None        # uid of anonymous user for shell
    gid      = None        # gid of anonymous user for shell
    clientwd = '/'
    filepath = None

    def __init__(self, user=None, tld=None):
        """Constructor
        @param user: the name of the user whose permissions we'll be using
        @type user: string
        """
        self.user     = user        # user name
        self.tld      = tld
        self.debug    = True

        # TODO: self.user needs to be set to something!!!
        if self.user is None:
            uid = os.getuid()
            self.user = pwd.getpwuid(os.getuid())[0]
            self.getUserUIDAndGID()
        #if self.tld is not None:
            #self.filepath = python.FilePath(self.tld)

    def getUserUIDAndGID(self):
        """used to set up permissions checking. finds the uid and gid of 
        the shell.user. called during __init__
        """
        log.msg('getUserUIDAndGID')
        pw_name, pw_passwd, pw_uid, pw_gid, pw_dir = range(5)
        try:
            p = pwd.getpwnam(self.user)
            self.uid, self.gid = p[pw_uid], p[pw_gid]
            log.debug("set (uid,gid) for file-permissions checking to (%s,%s)" % (self.uid,self.gid))
        except KeyError, (e,):
            log.msg("""
COULD NOT SET ANONYMOUS UID! Name %s could not be found.
We will continue using the user %s.
""" % (self.user, pwd.getpwuid(os.getuid())[pw_name]))


    def pwd(self):
        return self.clientwd

    def myjoin(self, lpath, rpath):
        """does a dumb join between two path elements, ensuring
        there is only one '/' between them. pays no attention to the
        filesystem, unlike os.path.join
        
        @param lpath: path element to the left of the '/' in the result
        @type lpath: string
        @param rpath: path element to the right of the '/' in the result
        @type rpath: string
        """
        if lpath and lpath[-1] == os.sep:
            lpath = lpath[:-1]
        if rpath and rpath[0] == os.sep:
            rpath = rpath[1:]
        return "%s%s%s" % (lpath, os.sep, rpath)

    def mapCPathToSPath(self, rpath):
        if not rpath or rpath[0] != '/':      # if this is not an absolute path
            # add the clients working directory to the requested path
            mappedClientPath = self.myjoin(self.clientwd, rpath) 
        else:
            mappedClientPath = rpath
        # next add the client's top level directory to the requested path
        mappedServerPath = self.myjoin(self.tld, mappedClientPath)
        ncpath, nspath = os.path.normpath(mappedClientPath), os.path.normpath(mappedServerPath)
        common = os.path.commonprefix([self.tld, nspath])
        if common != self.tld:
            raise PathBelowTLDError('Cannot access below / directory')
        if not os.path.exists(nspath):
            raise FileNotFoundError(nspath)
        return (mappedClientPath, mappedServerPath)
 
    def cwd(self, path):
        cpath, spath = self.mapCPathToSPath(path)
#        log.debug(cpath, spath)
        if os.path.exists(spath) and os.path.isdir(spath):
            self.clientwd = cpath
        else:
            raise FileNotFoundError(cpath)
       
    def cdup(self):
        self.cwd('..')

    def dele(self, path):
        raise AnonUserDeniedError()
        
    def mkd(self, path):
        raise AnonUserDeniedError()
        
    def rmd(self, path):
        raise AnonUserDeniedError()
 
    def retr(self, path):
        import os.path as osp
        cpath, spath = self.mapCPathToSPath(path)
        if not osp.isfile(spath):
            raise FileNotFoundError(cpath)
        #if not _testPermissions(self.uid, self.gid, spath):
            #raise PermissionDeniedError(cpath)
        try:
            return (file(spath, 'rb'), os.path.getsize(spath))
        except (IOError, OSError), (e,):
            log.debug(e)
            raise OperationFailedError('An error occurred %s' % e)

    def stor(self, params):
        raise AnonUserDeniedError()

    def getUnixLongListString(self, spath):
        """generates the equivalent output of a unix ls -l path, but
        using python-native code. 

        @param path: the path to return the listing for
        @type path: string
        @attention: this has only been tested on posix systems, I don't
            know at this point whether or not it will work on win32
        """
        import pwd, grp, time

        TYPE, PMSTR, NLINKS, OWN, GRP, SZ, MTIME, NAME = range(8)

        if os.path.isdir(spath):
#            log.debug('list path isdir')
            dlist = os.listdir(spath)
#            log.debug(dlist)
            dlist.sort()
        else:
#            log.debug('list path is not dir')
            dlist = [spath]

        pstat = None
        result = []
        sio = StringIO()
        maxNameWidth, maxOwnWidth, maxGrpWidth, maxSizeWidth, maxNlinksWidth = 0, 0, 0, 0, 0
        

        for item in dlist:
            try:
                pstat = os.lstat(os.path.join(spath, item))

                # this is exarkun's bit of magic
                fmt = 'pld----'
                pmask = lambda mode: ''.join([mode & (256 >> n) and 'rwx'[n % 3] or '-' for n in range(9)])
                dtype = lambda mode: [fmt[i] for i in range(7) if (mode >> 12) & (1 << i)][0]

                type = dtype(pstat.st_mode)
                pmstr = pmask(pstat.st_mode)
                nlinks = str(pstat.st_nlink)
                owner = _callWithDefault([str(pstat.st_uid)], pwd.getpwuid, pstat.st_uid)[0]
                group = _callWithDefault([str(pstat.st_gid)], grp.getgrgid, pstat.st_gid)[0]
                size = str(pstat.st_size)
                mtime = time.strftime('%b %d %I:%M', time.gmtime(pstat.st_mtime))
                name = os.path.split(item)[1]
                unixpms = "%s%s" % (type,pmstr)
            except (OSError, KeyError), e:
                log.debug(e)
                continue
            if len(name) > maxNameWidth:
                maxNameWidth = len(name)
            if len(owner) > maxOwnWidth:
                maxOwnWidth = len(owner)
            if len(group) > maxGrpWidth:
                maxGrpWidth = len(group)
            if len(size) > maxSizeWidth:
                maxSizeWidth = len(size)
            if len(nlinks) > maxNlinksWidth:
                maxNlinksWidth = len(nlinks)
            result.append([type, pmstr, nlinks, owner, group, size, mtime, name])

        for r in result:
            r[OWN]  = r[OWN].ljust(maxOwnWidth)
            r[GRP]  = r[GRP].ljust(maxGrpWidth)
            r[SZ]   = r[SZ].rjust(maxSizeWidth)
            #r[NAME] = r[NAME].ljust(maxNameWidth)
            r[NLINKS] = r[NLINKS].rjust(maxNlinksWidth)
            sio.write('%s%s %s %s %s %s %8s %s\n' % tuple(r))

        sio.seek(0)
        return sio
       
    def list(self, path):
        cpath, spath = self.mapCPathToSPath(path)
#        log.debug('cpath: %s,   spath:%s' % (cpath, spath))
        #if not _testPermissions(self.uid, self.gid, spath):
            #raise PermissionDeniedError(cpath)
        sio = self.getUnixLongListString(spath)
        return (sio, len(sio.getvalue()))

    def mdtm(self, path):
        from stat import ST_MTIME
        cpath, spath = self.mapCPathToSPath(path)
        if not os.path.isfile(spath):
            raise FileNotFoundError(spath)
        try:
            dtm = time.strftime("%Y%m%d%H%M%S", time.gmtime(os.stat(spath)[ST_MTIME]))
        except OSError, (e,):
            log.err(e)
            raise OperationFailedError(e)
        else:
            return dtm

    def size(self, path):
        """returns the size in bytes of path"""
        cpath, spath = self.mapCPathToSPath(path)
        if not os.path.isfile(spath):
            raise FileNotFoundError(spath)
        return os.path.getsize(spath)
   
    def nlist(self, path):
        raise CmdNotImplementedError()

class Shell(AnonymousShell):
    def dele(self, path):
        pass

    def mkd(self, path):
        pass

    def rmd(self, path):
        pass

    def stor(self, path):
        cpath, spath = self.mapCPathToSPath(path)
        if os.access(spath, os.W_OK):
            try:
                return file(spath, 'wb')
            except (IOError, OSError), (e,):
                log.debug(e)
                raise OperationFailedError('An error occurred %s' % e)
        raise PermissionDeniedError('Could not write file %s' % cpath)

class Realm:
    __implements__ = (portal.IRealm,)
    clientwd = '/'
    user = 'anonymous'
    logout = None
    tld = None          

    def __init__(self, tld=None, logout=None):
        """constructor
        @param tld: the top-level (i.e. root) directory on the server
        @type tld: string
        @attention: you *must* set tld somewhere before using the avatar!!
        @param logout: a special logout routine you want to be run when the user
            logs out (cleanup)
        @type logout: a function/method object
        """
        self.tld = tld
        self.logout = logout

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IShell in interfaces:
            if self.tld is None:
                raise ftp.TLDNotSetInRealmError("you must set FTPRealm's tld to a non-None value before creating avatars!!!")
            avatar = AnonymousShell(user=self.user, tld=self.tld)
            avatar.clientwd = self.clientwd
            avatar.logout = self.logout
            return IShell, avatar, avatar.logout
        log.msg('interfaces %s' % interfaces)
        raise NotImplementedError("Only IShell interface is supported by this realm")


