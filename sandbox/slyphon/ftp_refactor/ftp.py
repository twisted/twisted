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

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error, defer
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic, policies
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter

from twisted import application, internet, python
from twisted.python import failure, log, components

from twisted.cred import error, portal, checkers, credentials

# constants

# transfer modes
PASV = 1
PORT = 2

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
SYS_STATUS_OR_HELP_REPLY                = "211"
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
CMD_NOT_IMPLMNTD_FOR_ARG                = "504"
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
    CMD_NOT_IMPLMNTD_FOR_ARG:           "504 Not implemented for argument '%s'.",
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

class Error(Exception):
    pass

class TimeoutError(Exception):
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

# -- DTP Protocol --

class DTPFileSender(basic.FileSender):
    def resumeProducing(self):
        chunk = ''
        if self.file:
            chunk = self.file.read(self.CHUNK_SIZE)
            #log.debug('chunk: %s' % chunk)
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

class DTPFileReceiver(protocol.ProcessProtocol):
    def __init__(self):
        pass

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

class DTP(object, protocol.Protocol):
    # The Data Transfer Protocol for this FTP-PI instance
    #   all dtp_* methods return a deferred
    isConnected = False 
    reTransform = re.compile(r'(?<!\r)\n') # says, match an \n that's not immediately preceeded by a \r

    def connectionMade(self):
        # Will start an transfer, if one is queued up, 
        # when the client connects
        self.pi.setTimeout(None)        # don't timeout as long as we have a connection
        peer = self.transport.getPeer()
        self.isConnected = True

        if self.factory.peerCheck and peer[1] != self.pi.peerHost[1]:
            # DANGER Will Robinson! Bailing!
            log.debug('dtp ip did not match ftp ip')
            d.errback(BogusClientError("%s != %s" % (peer[1], self.pi.peerHost[1])))   
            return

        log.debug('firing dtpFactory deferred')
        d, self.factory.deferred = self.factory.deferred, defer.Deferred()
        d.callback(None)

    def dataReceived(self, data):
        if self.pi.fp is not None:
            self.pi.fp.write(data)
            self.pi.fp.flush()

    def transformChunk(self, chunk):
        # this is b0rK3n! send everything as BINARY!
        return chunk
        #log.msg('transformChunk: before = %s' % chunk)
        #newChunk = self.reTransform.sub('\r\n', chunk)
        #log.msg('transformChunk: after = %s' % newChunk)
        #return newChunk

    def dtp_RETR(self): # RETR = sendFile
        # sends a file object out the wire
        # 
        filename = _getFPName(self.pi.fp)

        log.debug('sendfile sending %s' % filename)

        fs = DTPFileSender()
        if self.pi.binary:
            transform = None
        else:
            transform = self.transformChunk
        
        # lets set self.pi.fp file pointer to 0 just to 
        # make sure the avatar didn't forget, hmm?
        self.pi.fp.seek(0)
        
        return fs.beginFileTransfer(self.pi.fp, self.transport, transform
                ).addCallback(debugDeferred,'firing at end of file transfer'
                ).addCallback(self._dtpPostTransferCleanup
                )

    def dtp_STOR(self):
        pass

    def _dtpPostTransferCleanup(self, *arg):
        log.debug("dtp._dtpPostTransferCleanup")
        self.transport.loseConnection()

    def connectionLost(self, reason):
        log.debug('dtp.connectionLost: %s' % reason)
        self.pi.finishedFileTransfer()
        self.isConnected = False

class DTPFactory(protocol.Factory): 
    # -- configuration variables --
    peerCheck = True

    # -- class variables --
    def __init__(self, pi, peerHost=None):
        self.pi = pi                        # the protocol interpreter that is using this factory
        self.peerHost = peerHost            # the from FTP.transport.peerHost()
        self.deferred = defer.Deferred()    # deferred will fire when instance is connected
        self.delayedCall = None

    def buildProtocol(self, addr):
        log.debug('DTPFactory.buildProtocol')
        self.cancelTimeout()
        if self.pi.dtpInstance:   # only create one instance
            return 
        p = DTP()
        p.factory = self
        p.pi = self.pi
        self.pi.dtpInstance = p
        return p

    def stopFactory(self):
        log.debug('dtpFactory.stopFactory')
        self.cancelTimeout()

    def timeoutFactory(self):
        log.msg('timed out waiting for DTP connection')
        if self.deferred:
            d, self.deferred = self.deferred, None 

            # TODO: LEFT OFF HERE!

            d.addErrback(debugDeferred, 'timeoutFactory firing errback')
            d.errback(defer.TimeoutError())
        self.stopFactory()

    def cancelTimeout(self):
        if not self.delayedCall.called and not self.delayedCall.cancelled: 
            log.debug('cancelling DTP timeout')
            self.delayedCall.cancel()
            assert self.delayedCall.cancelled
            log.debug('timeout has been cancelled')

    def setTimeout(self, seconds):
        log.msg('DTPFactory.setTimeout set to %s seconds' % seconds)
        self.delayedCall = reactor.callLater(seconds, self.timeoutFactory)

# -- FTP-PI (Protocol Interpreter) --


def cleanPath(path):
    # cleanup backslashes and multiple foreslashes
    log.debug("pre-cleaned path: %s" % path)
    if path:
        path = re.sub(r'[\\]{2,}?', '/', path)
        path = re.sub(r'[/]{2,}?','/', path)
        path = re.sub(r'[*]?', '', path)
    path = os.path.normpath(path)
    log.debug('cleaned path: %s' % path)
    return path

class FTP(object, basic.LineReceiver, policies.TimeoutMixin):      
    """the File Transfer Protocol"""
    # FTP is a bit of a misonmer, as this is the PI - Protocol Interpreter
    blockingCommands = ['RETR', 'STOR', 'LIST'] #, 'PORT'] <- #TODO add this when implemented properly
    reTelnetChars = re.compile(r'(\\x[0-9a-f]{2}){1,}')

    # how long the DTP waits for a connection
    dtpTimeout = 10

    # if this instance is the upper limit of instances allowed, then 
    # reply with appropriate error message and drop the connection
    instanceNum = 0

    portal      = None
    shell       = None     # the avatar
    user        = None     # the username of the client connected
    peerHost    = None     # the (type,ip,port) of the client
    dtpTxfrMode = None     # PASV or PORT, no default
    blocked     = None     # a command queue for pipelining
    dtpFactory  = None     # generates a single DTP for this session
    dtpInstance = None     # a DTP protocol instance
    dtpPort     = None     # object returned from listenTCP
    dtpInetPort = None     # result of dtpPort.getHost() used for saving inet port number
    dtpHostPort = None     # client address/port to connect to on PORT command
    dtpInterface = ''      # interface for dtp to listen/connect on/to

    binary      = True     # binary transfers? False implies ASCII. defaults to True

    def connectionMade(self):
        log.debug('ftp-pi connectionMade: instance %s' % self.instanceNum)

        # TODO: add tests for this!
        if (self.factory.maxProtocolInstances is not None and 
                self.instanceNum >= self.factory.maxProtocolInstances): 
            self.reply(TOO_MANY_CONNECTIONS)
            self.transport.loseConnection()
            return
        self.reply(WELCOME_MSG)                     
        self.peerHost = self.transport.getPeer()
        self.setTimeout(self.timeOut)
#        self.__testingautologin()

    def __testingautologin(self):
        import warnings; warnings.warn("""

            --> DEBUGGING CODE ACTIVE!!! <--
""")
        reactor._pi = self
        #lr = self.lineReceived
        #lr('USER anonymous')
        #lr('PASS f@d.com')
        #lr('PASV')
        #lr('LIST')
        #lr('RETR .vim/vimrc')
        #lr('RETR Session.vim')

    def connectionLost(self, reason):
        log.msg("Oops! lost connection\n %s" % reason)
        # if we have a DTP protocol instance running and
        # we lose connection to the client's PI, kill the 
        # DTP connection and close the port
        if self.dtpFactory:
            self.cleanupDTP()
        self.setTimeout(None)
        self.factory.currentInstanceNum -= 1
        if hasattr(self.shell, 'logout') and self.shell.logout is not None:
            self.shell.logout()
            
    def timeoutConnection(self):
        log.msg('FTP timed out')
        self.transport.loseConnection()
        #if self.dtpFactory is not None and self.dtpFactory.deferred is not None:
            #d, self.dtpFactory.deferred = self.dtpFactory.deferred, None
            #d.errback(TimeoutError('cleaning up dtp!'))

    def setTimeout(self, seconds):
        log.msg('ftp.setTimeout to %s seconds' % str(seconds))
        policies.TimeoutMixin.setTimeout(self, seconds)

    def reply(self, key, s=''):                                               
        # format a RESPONSE and send it out over the wire
        if string.find(RESPONSE[key], '%s') > -1:
            log.debug(RESPONSE[key] % s + ENDLN)
            self.transport.write(RESPONSE[key] % s + ENDLN)
        else:
            log.debug(RESPONSE[key] + ENDLN)
            self.transport.write(RESPONSE[key] + ENDLN)

    def lineReceived(self, line):
        # Process the input from the client
        self.resetTimeout()
        line = string.strip(line)
        log.debug(repr(line))
        line = self.reTelnetChars.sub('', line)  # clean up '\xff\xf4\xff' nonsense
        line = line.encode() 
        try:
            cmdAndArgs = line.split(' ',1)
            log.debug('processing command %s' % cmdAndArgs)
            self.processCommand(*cmdAndArgs)
        except CmdSyntaxError, (e,):
            self.reply(SYNTAX_ERR, e)
        except CmdArgSyntaxError, (e,):
            log.debug(e)
            self.reply(SYNTAX_ERR_IN_ARGS, e)
        except AnonUserDeniedError, (e,):
            log.debug(e)
            self.reply(ANON_USER_DENIED, e)
        except CmdNotImplementedError, (e,):
            log.debug(e)
            self.reply(CMD_NOT_IMPLMNTD, e)
        except CmdNotImplementedForArgError, (e,):
            log.debug(e)
            self.reply(CMD_NOT_IMPLMNTD_FOR_ARG, e)
        except BadCmdSequenceError, (e,): 
            log.debug(e)
            self.reply(BAD_CMD_SEQ, e)
        except AuthorizationError, (e,):
            log.debug(e)
            self.reply(AUTH_FAILURE, 'internal server error')
        except FileNotFoundError, (e,):
            log.debug(e)
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, (e,):
            log.debug(e)
            self.reply(PERMISSION_DENIED, e)
        except OperationFailedError, (e,):
            log.debug(e)
            self.reply(REQ_ACTN_NOT_TAKEN, '')
        except Exception, e:
            log.err(e)
            self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')
            raise

    def processCommand(self, cmd, *args):
        log.debug('FTP.processCommand: cmd = %s, args = %s' % (cmd,args))
        if self.blocked != None:                                                # all DTP commands block, 
            log.debug('FTP is queueing command: %s' % cmd)
            self.blocked.append((cmd,args))                                     # so queue new requests
            return

        cmd = cmd.upper()
        if cmd not in ['USER','PASS'] and not self.shell:                       # these are the only two commands that don't require
            log.debug('ftp_%s returning, user not logged in' % cmd)             # an authenticated user
            self.reply(NOT_LOGGED_IN)
            return

        if cmd in self.blockingCommands:                                        # if this is a DTP related command
            log.debug('FTP.processCommand: cmd %s in blockingCommands' % cmd)
            if not self.dtpInstance:                                            # if no one has connected yet
                log.debug('FTP.processCommand: self.dtpInstance = %s' % self.dtpInstance)
                # a bit hackish, but manually blocks this command 
                # until we've set up the DTP protocol instance
                # _unblock will run this first command and subsequent
                self.blocked = [(cmd,args)]                                     # add item to queue and start blocking
                log.debug('during dtp setup, blocked = %s' % self.blocked)
                return
        method = getattr(self, "ftp_%s" % cmd, None)                            # try to find the method in this class
        log.debug('FTP.processCommand: method = %s' % method)
        if method:
            return method(*args)                                                
        raise CmdNotImplementedError(cmd)                 # if we didn't find cmd, raise an error and alert client

    def _unblock(self, *_):
        log.debug('_unblock running')                                           # unblock commands
        commands = self.blocked                                                 
        self.blocked = None                                                     # reset blocked to allow new commands
        while commands and self.blocked is None:                                # while no other method has set self.blocked
            cmd, args = commands.pop(0)                                         # pop a command off the queue
            self.processCommand(cmd, *args)                                     # and process it
        if self.blocked is not None:                                            # if someone has blocked during the time we were processing
            self.blocked.extend(commands)                                       # add our commands that we dequeued back into the queue

    def _createDTP(self):
        self.setTimeout(None)     # don't timeOut when setting up DTP
        log.debug('_createDTP')
        if not self.dtpFactory:
            phost = self.transport.getPeer()[1]
            self.dtpFactory = DTPFactory(pi=self, peerHost=phost)
            self.dtpFactory.setTimeout(self.dtpTimeout)
        if not hasattr(self, '_FTP__TestingSoJustSkipTheReactorStep'):    # to allow for testing
            if self.dtpTxfrMode == PASV:    
                self.dtpPort = reactor.listenTCP(0, self.dtpFactory, interface=self.dtpInterface)
            elif self.dtpTxfrMode == PORT: 
                self.dtpPort = reactor.connectTCP(self.dtpHostPort[1], self.dtpHostPort[2])
            else:
                log.err('SOMETHING IS SCREWY: _createDTP')

        d = self.dtpFactory.deferred        
        d.addCallback(debugDeferred, 'dtpFactory deferred')
        d.addCallback(self._unblock)                            # VERY IMPORTANT: call _unblock when client connects
        d.addErrback(self._ebDTP)

    def _ebDTP(self, error):
        log.msg(error)
        self.setTimeout(self.factory.timeOut)       # restart timeOut clock after DTP returns
        r = error.trap(defer.TimeoutError,          # this is called when DTP times out
                       BogusClientError,            # called if PI & DTP clients don't match
                       TimeoutError,             # called when FTP connection times out
                       ClientDisconnectError)       # called if client disconnects prematurely during DTP transfer
                       
        if r == defer.TimeoutError:                     
            self.reply(CANT_OPEN_DATA_CNX)
        elif r in (BogusClientError, TimeoutError):
            self.reply(SVC_NOT_AVAIL_CLOSING_CTRL_CNX)
            self.transport.loseConnection()
        elif r == ClientDisconnectError:
            self.reply(CNX_CLOSED_TXFR_ABORTED)

        # if we timeout, or if an error occurs, 
        # all previous commands are junked
        self.blocked = None                         
        
    def cleanupDTP(self):
        # called when DTP connection exits
        
        log.debug('cleanupDTP')

        dtpPort, self.dtpPort = self.dtpPort, None
        try:
            dtpPort.stopListening()
        except AttributeError, (e,):
            log.msg('Already Called dtpPort.stopListening!!!: %s' % e)

        self.dtpFactory.stopFactory()
        if self.dtpFactory is None:
            log.debug('ftp.dtpFactory already set to None')
        else:
            self.dtpFactory = None

        if self.dtpInstance is None:
            log.debug('ftp.dtpInstance already set to None')
        else:
            self.dtpInstance = None

        # TODO: Is this the right place for clearing dtpCommand?
        self.dtpCommand = None

    def _doDTPCommand(self, cmd, *arg): 
        self.setTimeout(None)               # don't Time out when waiting for DTP Connection
        log.debug('FTP._doDTPCommand: self.blocked: %s' % self.blocked)
        if self.blocked is None:
            self.blocked = []
        try:
            f = getattr(self.dtpInstance, "dtp_%s" % cmd, None)
            log.debug('running dtp function %s' % f)
        except AttributeError, e:
            log.err('SOMETHING IS SCREWY IN _doDTPCommand')
            raise e
        else:
            self.dtpFactory.setTimeout(self.dtpTimeout)
            self.dtpCommand = cmd
            if arg:
                d = f(arg)
            else:
                d = f()
            d.addCallback(debugDeferred, 'deferred returned to _doDTPCommand has fired')
            d.addCallback(lambda _: self._cbDTPCommand())
            d.addCallback(debugDeferred, 'running cleanupDTP')
            d.addCallback(lambda _: self.cleanupDTP())
            d.addCallback(debugDeferred, 'running ftp.setTimeout()')
            d.addCallback(lambda _: self.setTimeout(self.factory.timeOut))
            d.addCallback(debugDeferred, 'running ftp._unblock')
            d.addCallback(lambda _: self._unblock())
            d.addErrback(self._ebDTP)

    def finishedFileTransfer(self, *arg):
        # called back when a file transfer has been completed by the dtp
        log.debug('finishedFileTransfer! cleaning up DTP')
        if self.fp is not None and not self.fp.closed:
            if ((self.dtpCommand == 'RETR' and self.fp.tell() == self.fpsize)
               or self.dtpCommand == 'STOR'):
                log.debug('transfer completed okay :-)')
                self.reply(TXFR_COMPLETE_OK)
            else:
                log.debug("uh-oh there was an error...must have been the client's fault")
                self.reply(CNX_CLOSED_TXFR_ABORTED)
            self.fp.flush()
            self.fp.close()
            self.fp = None

    def _cbDTPCommand(self):
        # called back when any DTP command has completed successfully
        log.debug("DTP Command success")

    def ftp_USER(self, params=None):
        # Get the login name, and reset the session
        # PASS is expected to follow
        # 
        # @note: from the rfc: The argument field is a Telnet string identifying
        # the user.  The user identification is that which is required by the
        # server for access to its file system.  This command will normally be
        # the first command transmitted by the user after the control connections
        # are made
        # 
        # This has the effect of flushing any user, password, and account
        # information already supplied and beginning the login sequence again.
        # All transfer parameters are unchanged and any file transfer in progress
        # is completed under the old access control parameters.

        if not params:
            raise CmdSyntaxError('USER with no parameters')
        self.user = string.split(params)[0]
        log.debug('ftp_USER params: %s' % params)
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)

    # TODO: add max auth try before timeout from ip...
    # TODO: need to implement minimal ABOR command

    def ftp_PASS(self, params=''):
        # Authorize the USER and the submitted password
        #
        # @note: from the rfc: The argument field is a Telnet string specifying
        # the user's password.  This command must be immediately preceded by the
        # user name command, and, for some sites, completes the user's
        # identification for access control.

        # the difference between an Anon login and a User login is 
        # the avatar that will be returned to the callback
        if not self.user:
            raise BadCmdSequenceError('USER required before PASS')

        log.debug('ftp_PASS params: %s' % params)

        if params == '':
            raise CmdArgSyntaxError('you must specify a password with PASS')
        
        self.passwd = params.split()[0]        # parse password 

        import ftp
        # if this is an anonymous login
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.passwd = params
            if self.portal:
                self.portal.login(
                        credentials.Anonymous(), 
                        None, 
                        ftp.IShell
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
                        ftp.IShell
                    ).addCallbacks(self._cbLogin, self._ebLogin
                    )
            else:
                raise AuthorizationError('internal server error')

    def _cbAnonLogin(self, (interface, avatar, logout)):
        # sets up anonymous login avatar
        import ftp
        assert interface is ftp.IShell
        peer = self.transport.getPeer()
        #log.debug("Anonymous login from %s:%s" % (peer[1], peer[2]))
        self.shell = avatar
        self.logout = logout
        self.reply(GUEST_LOGGED_IN_PROCEED)

    def _cbLogin(self, (interface, avatar, logout)):
        # sets up authorized user login avatar
        assert interface is IShell
        self.shell = avatar
        self.logout = logout
        self.reply(USR_LOGGED_IN_PROCEED)

    def _ebLogin(self, failure):
        r = failure.trap(error.UnauthorizedLogin, TLDNotSetInRealmError)
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
        # This command causes a list to be sent from the server to the
        # passive DTP.  If t he pathname specifies a directory or other
        # group of files, the server should transfer a list of files
        # in the specified directory.  If the pathname specifies a
        # file then the server should send current information on the
        # file.  A null argument implies the user's current working or
        # default directory.
        log.debug('ftp_LIST: %s' % params)
        if params == "-a": params = ''  # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15

        self.fp, self.fpsize = self.shell.list(cleanPath(params))    # returns a StringIO object
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR')

    def ftp_SIZE(self, params=''):
        log.debug('ftp_SIZE: %s' % params)
        filesize = self.shell.size(cleanPath(params))
        self.reply(FILE_STATUS, filesize)

    def ftp_MDTM(self, params=''):
        log.debug('ftp_MDTM: %s' % params)
        dtm = self.shell.mdtm(cleanPath(params))
        self.reply(FILE_STATUS, dtm)
 
    def ftp_PWD(self, params=''):
        # Print working directory command
        self.reply(PWD_REPLY, self.shell.pwd())

    def ftp_PASV(self):
        # Request for a passive connection
        #
        # reply is in format 227 =h1,h2,h3,h4,p1,p2
        #
        # note: from the rfc: This command requests the server-DTP to "listen"
        # on a data port (which is not its default data port) and to wait for a
        # connection rather than initiate one upon receipt of a transfer command.
        # The response to this command includes the host and port address this
        # server is listening on.
        #
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
        log.debug('ftp_PASV') 
        self.dtpTxfrMode = PASV
        if self.dtpFactory:                 # if we have a DTP port set up
            self.cleanupDTP()               # lose it 
        if not self.dtpFactory:             # if we haven't set up a DTP port yet (or just closed one)
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

    def decodeHostPort(line):
        # Decode an FTP response specifying a host and port.
        # 
        # see RFC sec. 4.1.2 "PASV"
        #
        # @returns: a 2-tuple of (host, port).
         
        #abcdef = re.sub('[^0-9, ]', '', line[4:])
        abcdef = re.sub('[^0-9, ]', '', line)
        a, b, c, d, e, f = map(str.strip, abcdef.split(','))
        host = "%s.%s.%s.%s" % (a, b, c, d)
        port = (int(e)<<8) + int(f)
        return (host, port)

    decodeHostPort = staticmethod(decodeHostPort)

    def ftp_PORT(self, params=None):
        self.reply(CMD_NOT_IMPLMNTD, 'PORT')
        return
        # XXX: This is b0rk3n for now
        log.debug('ftp_PORT')
        self.dtpTxfrMode = PORT
        self.dtpHostPort = self.decodeHostPort(params)
        if self.dtpFactory:                 # if we have a DTP port set up
            self.cleanupDTP()               # lose it 
        if not self.dtpFactory:             # if we haven't set up a DTP port yet (or just closed one)
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
        if self.dtpTxfrMode is None:
            raise BadCmdSequenceError('must send PORT or PASV before RETR')
        self.fp, self.fpsize = self.shell.retr(cleanPath(params))
        log.debug('self.fp = %s, self.fpsize = %s' % (self.fp, self.fpsize))
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR')

    def ftp_STRU(self, params=""):
        p = params.upper()
        if params == 'F':
            return self.reply(CMD_OK)
        raise CmdNotImplementedForArgError(params)

    def ftp_MODE(self, params=""):
        p = params.upper()
        if params == 'S':
            return self.reply(CMD_OK)
        raise CmdNotImplementedForArgError(params)

    def ftp_QUIT(self, params=''):
        self.transport.loseConnection()
        log.debug("Client Quit")

    def ftp_DELE(self, path=''):
        self.shell.dele(path)
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)
        
    def ftp_MKD(self, path=''):
        self.shell.mkd(path)
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_RMD(self, path=''):
        self.shell.rmd(path)
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_STOR(self, path=''):
        if self.dtpTxfrMode is None:
            raise BadCmdSequenceError('must send PORT or PASV before RETR')
        self.fp = self.shell.stor(cleanPath(path))       
        if self.dtpInstance and self.dtpInstance.isConnected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('STOR')

    def ftp_STOU(self, path=''):
        self.reply(CMD_NOT_IMPLMNTD, 'STOU')

class Factory(protocol.Factory):
    """A factory for producing ftp protocol instances
    @ivar maxProtocolInstances: the maximum number of FTP protocol instances
        this factory will create. When the maximum number is reached, a protocol
        instance will be spawned that will give the "Too many connections" message
        to the client and then close the connection.
    @ivar timeOut: the protocol interpreter's idle timeout time in seconds, default is 600 seconds
    """
    protocol = FTP
    allowAnonymous = True
    userAnonymous = 'anonymous'        
    timeOut = 600

    maxProtocolInstances = None
    currentInstanceNum = 0
    instances = []

    def __init__(self):
        pass
        #reactor._pi = self         # for debugging

    def buildProtocol(self, addr):
        log.debug('%s of %s max ftp instances: ' % (self.currentInstanceNum, self.maxProtocolInstances))
        pi            = protocol.Factory.buildProtocol(self, addr)
        pi.protocol   = self.protocol
        pi.portal     = self.portal
        pi.timeOut    = Factory.timeOut
        pi.factory    = self
        if self.maxProtocolInstances is not None:
            self.currentInstanceNum += 1
            pi.instanceNum = self.currentInstanceNum
        self.instances.append(pi)
        return pi

    def stopFactory(self):
        # make sure ftp instance's timeouts are set to None
        # to avoid reactor complaints
        [p.setTimeout(None) for p in self.instances if p.timeOut is not None]
 
class IFile(components.Interface):
    """An interface to a file object or a file-like object
    
    most of this documentation taken verbatim from the python standard library documentation
    section 2.2.8 - File Objects

    @note: (from the stdlib) File objects also offer a number of other interesting attributes. These
    are not required for file-like objects, but should be implemented if
    they make sense for the particular object.
    
    @ivar closed: bool indicating the current state of the file object.
    @ivar name: If the file object was created using open(), the name of the
    file. Otherwise, some string that indicates the source of the file object,
    of the form "<...>". 
    """

    def close(self):
        """closes the file. A closed file cannot be read or written any more."""
        pass
    
    def seek(self, pos, mode = 0):
        """ Set the file's current position, like stdio's fseek(). The whence
        argument is optional and defaults to 0  (absolute file positioning);
        other values are 1 (seek relative to the current position) and 2 (seek
        relative to the file's end). There is no return value. 
        """
        pass

    def tell(self):
        """ Return the file's current position, like stdio's ftell().
        """
        pass

class IReadableFile(IFile):
    """An interface to a file object or a file-like object opened for reading
    
    most of this documentation taken verbatim from the python standard library documentation
    section 2.2.8 - File Objects

    @note: (from the stdlib) File objects also offer a number of other
    interesting attributes. These are not required for file-like objects, but
    should be implemented if they make sense for the particular object.
    
    @ivar closed: bool indicating the current state of the file object.
    @ivar name: If the file object was created using open(), the name of the
                file. Otherwise, some string that indicates the source of the file object,
                of the form "<...>". 
    """

    def getvalue(self):
        """Retrieve the entire contents of the "file" at any time before
        the object's close() method is called.
        """
        pass

    def read(self, size=-1):
        """ Read at most size bytes from the file (less if the read hits EOF
        before obtaining size bytes). If the size  argument is negative or
        omitted, read all data until EOF is reached. The bytes are returned as
        a string object. An empty string is returned when EOF is encountered
        immediately. 
        """
        pass

class IWriteableFile(IFile):
    """An interface to a file object or a file-like object opened for writing 
    
    most of this documentation taken verbatim from the python standard library documentation
    section 2.2.8 - File Objects

    @note: (from the stdlib) File objects also offer a number of other
    interesting attributes. These are not required for file-like objects, but
    should be implemented if they make sense for the particular object.
    
    @ivar closed: bool indicating the current state of the file object.
    @ivar name: If the file object was created using open(), the name of the
                file. Otherwise, some string that indicates the source of the file object,
                of the form "<...>". 
    """

    def flush(self):
        """Flush the internal buffer, like stdio's fflush(). This may be a no-op on some file-like objects.  """
        pass

    def write(self, s):
        """ Write a string to the file. There is no return value. Due to
        buffering, the string may not actually show up in the file until the
        flush() or close() method is called.
        """
        pass

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

        @return: a tuple (cpath, spath) where cpath is the client's top level
        directory plus path, 

        @note: spath is cpath in relation to the server's filesystem. cpath is
        an illusion, spath is a real file in the filesystem
        """
        pass

    def pwd(self):
        """ Print working directory command
        """
        pass

    def cwd(self, path):
        """Change working directory

        @note: from the rfc: This command allows the user to work with a
        different directory or dataset for file storage or retrieval without
        altering his login or accounting information.  Transfer parameters are
        similarly unchanged.  The argument is a pathname specifying a directory
        or other system dependent file group designator.

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
        

        @note: from the rfc: This command causes a list to be sent from the
        server to the passive DTP.  If the pathname specifies a directory or
        other group of files, the server should transfer a list of files in the
        specified directory.  If the pathname specifies a file then the server
        should send current information on the file.  A null argument implies
        the user's current working or default directory.
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

class IHighLevelShell(components.Interface):
    '''a slightly higher level version of the ftp.Shell
    The FTP Shell is intended to mimic a unix shell to some extent. It's a layer on top of the 
    server filesystem, and you'll need to implement a way to convert paths as the client sees them
    into paths to resources on the server side. 
    
    All requests coming from the protocol are client-relative and denoted using
    the variable 'cpath', server-relative paths are given the variable 'spath'
    '''
    def sendFile(self, cpath):
        """a request from the client to send a file to this machine
        @param cpath: a client-relative path
        @type cpath: string
        @returns: an C{IWriteableFile} implementor opened for the correct spath
        @raise AnonUserDeniedError: when an anonymous user tries to execute this command
        @raise PermissionDeniedError: when the user has insufficient permissions to write a resource to 
            the indicated cpath
        @raise OperationFailedError: when an error occurs saving the resource. 
        """
        pass

    def retrieveFile(self, cpath):
        """a request that you send the resource at cpath to the client over the DTP 
        connection
        @param cpath: a client-relative path, the file to send to the client
        @type cpath: string
        @returns: a tuple of a (C{IReadableFile} implementor, size as int)
        @rtype: tuple
        @raises FileNotFoundError: when cpath does not represent a valid resource on the server
        @raise PermissionDeniedError: when the user has insufficient permissions to read the resource at cpath
        @raises OperationFailedError: when any os-related error occurs when attempting to send the resource
        """
        pass

    def deleteFile(self, cpath):
        """a request that the server remove a file at cpath
        @raise AnonUserDeniedError: when an anonymous user tries to execute this command
        @raise PermissionDeniedError: when the user has insufficient permissions to remove the file at the indicated cpath
        @raise OperationFailedError: when an error occurs removing the file.
        """
        pass

    def makeDirectory(self, cpath):
        """a request that the server create a directory-type structure at cpath
        @raise AnonUserDeniedError: when an anonymous user tries to execute this command
        @raise PermissionDeniedError: when the user has insufficient permissions to create a directory at the indicated cpath
        @raise OperationFailedError: when an error occurs creating the directory. 
        """
        pass

    def removeDirectory(self, cpath):
        """a request that the server remove a directory-type structure at cpath
        @raise AnonUserDeniedError: when an anonymous user tries to execute this command
        @raise PermissionDeniedError: when the user has insufficient permissions to remove a directory at the indicated cpath
        @raise OperationFailedError: when an error occurs removing a directory.
        """
        pass



# --- FTP CLIENT  -------------------------------------------------------------

from twisted.internet.defer import Deferred, DeferredList, FAILURE
from twisted.python.failure import Failure
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer

####
# And now for the client...

# Notes:
#   * Reference: http://cr.yp.to/ftp.html
#   * FIXME: Does not support pipelining (which is not supported by all
#     servers anyway).  This isn't a functionality limitation, just a
#     small performance issue.
#   * Only has a rudimentary understanding of FTP response codes (although
#     the full response is passed to the caller if they so choose).
#   * Assumes that USER and PASS should always be sent
#   * Always sets TYPE I  (binary mode)
#   * Doesn't understand any of the weird, obscure TELNET stuff (\377...)

class Error(Exception):
    pass

class ConnectionLost(Error):
    pass

class CommandFailed(Error):
    pass

class BadResponse(Error):
    pass

class UnexpectedResponse(Error):
    pass

class Command:
    def __init__(self, text=None, public=0):
        self.text = text
        self.deferred = Deferred()
        self.ready = 1
        self.public = public

    def fail(self, failure):
        if self.public:
            self.deferred.errback(failure)


class ProtocolWrapper(Protocol):
    def __init__(self, original, deferred):
        self.original = original
        self.deferred = deferred
    def makeConnection(self, transport):
        self.original.makeConnection(transport)
    def dataReceived(self, data):
        self.original.dataReceived(data)
    def connectionLost(self, reason):
        self.original.connectionLost(reason)
        # Signal that transfer has completed
        self.deferred.callback(None)
    def connectionFailed(self):
        self.deferred.errback(Failure(Error('Connection failed')))


class SenderProtocol(Protocol):
    __implements__ = Protocol.__implements__ + (IFinishableConsumer,)

    def __init__(self):
        # Fired upon connection
        self.connectedDeferred = Deferred()

        # Fired upon disconnection
        self.deferred = Deferred()

    #Protocol stuff
    def dataReceived(self, data):
        assert 0, ("We received data from the server - "
                   "this shouldn't happen.")

    def makeConnection(self, transport):
        Protocol.makeConnection(self, transport)
        self.connectedDeferred.callback(self)
        
    def connectionLost(self, reason):
        if reason.check(error.ConnectionDone):
            self.deferred.callback('connection done')
        else:
            self.deferred.errback(reason)

    #IFinishableConsumer stuff
    def write(self, data):
        self.transport.write(data)

    def registerProducer(self):
        pass

    def unregisterProducer(self):
        pass

    def finish(self):
        self.transport.loseConnection()
    
    
def decodeHostPort(line):
    """Decode an FTP response specifying a host and port.

    @returns: a 2-tuple of (host, port).
    """
    abcdef = re.sub('[^0-9, ]', '', line[4:])
    a, b, c, d, e, f = map(str.strip, abcdef.split(','))
    host = "%s.%s.%s.%s" % (a, b, c, d)
    port = (int(e)<<8) + int(f)
    return host, port


class DataPortFactory(ServerFactory):
    """Factory for data connections that use the PORT command
    
    (i.e. "active" transfers)
    """
    noisy = 0
    def buildProtocol(self, connection):
        # This is a bit hackish -- we already have a Protocol instance,
        # so just return it instead of making a new one
        # FIXME: Reject connections from the wrong address/port
        #        (potential security problem)
        self.protocol.factory = self
        self.port.loseConnection()
        return self.protocol


class Client(basic.LineReceiver):
    """A Twisted FTP Client

    Supports active and passive transfers.

    This class is semi-stable.

    @ivar passive: See description in __init__.
    """
    debug = 0
    def __init__(self, username='anonymous', 
                 password='twisted@twistedmatrix.com',
                 passive=1):
        """Constructor.

        I will login as soon as I receive the welcome message from the server.

        @param username: FTP username
        @param password: FTP password
        @param passive: flag that controls if I use active or passive data
            connections.  You can also change this after construction by
            assigning to self.passive.
        """
        self.username = username
        self.password = password

        self.actionQueue = []
        self.nextDeferred = None
        self.queueLogin()
        self.response = []

        self.passive = passive

    def fail(self, error):
        """Disconnect, and also give an error to any queued deferreds."""
        self.transport.loseConnection()
        while self.actionQueue:
            ftpCommand = self.popCommandQueue()
            ftpCommand.fail(Failure(ConnectionLost('FTP connection lost', error)))
        return error

    def sendLine(self, line):
        """(Private) Sends a line, unless line is None."""
        if line is None:
            return
        basic.LineReceiver.sendLine(self, line)

    def sendNextCommand(self):
        """(Private) Processes the next command in the queue."""
        ftpCommand = self.popCommandQueue()
        if ftpCommand is None:
            self.nextDeferred = None
            return
        if not ftpCommand.ready:
            self.actionQueue.insert(0, ftpCommand)
            reactor.callLater(1.0, self.sendNextCommand)
            self.nextDeferred = None
            return
        if ftpCommand.text == 'PORT':
            self.generatePortCommand(ftpCommand)
        if self.debug:
            log.msg('<-- %s' % ftpCommand.text)
        self.nextDeferred = ftpCommand.deferred
        self.sendLine(ftpCommand.text)

    def queueLogin(self):
        """Initialise the connection.

        Login, send the password, set retrieval mode to binary"""
        self.nextDeferred = Deferred().addErrback(self.fail)
        for command in ('USER ' + self.username, 
                        'PASS ' + self.password,
                        'TYPE I',):
            d = self.queueStringCommand(command, public=0)
            # If something goes wrong, call fail
            d.addErrback(self.fail)
            # But also swallow the error, so we don't cause spurious errors
            d.addErrback(lambda x: None)
        
    def queueCommand(self, ftpCommand):
        """Add an Command object to the queue.

        If it's the only thing in the queue, and we are connected and we aren't
        waiting for a response of an earlier command, the command will be sent
        immediately.

        @param ftpCommand: an L{Command}
        """
        self.actionQueue.append(ftpCommand)
        if (len(self.actionQueue) == 1 and self.transport is not None and
            self.nextDeferred is None):
            self.sendNextCommand()

    def popCommandQueue(self):
        """Return the front element of the command queue, or None if empty."""
        if self.actionQueue:
            return self.actionQueue.pop(0)
        else:
            return None

    def receiveFromConnection(self, command, protocol):
        """
        Retrieves a file or listing generated by the given command,
        feeding it to the given protocol.

        @param command: string of an FTP command to execute then receive the
            results of (e.g. LIST, RETR)
        @param protocol: A L{Protocol} *instance* e.g. an
            L{FileListProtocol}, or something that can be adapted to one.
            Typically this will be an L{IConsumer} implemenation.

        @returns: L{Deferred}.
        """
        protocol = IProtocol(protocol)
        wrapper = ProtocolWrapper(protocol, Deferred())
        return self._openDataConnection(command, wrapper)

    def sendToConnection(self, command):
        """XXX
        
        @returns: A tuple of two L{Deferred}s:
                  - L{Deferred} L{IFinishableConsumer}. You must call
                    the C{finish} method on the IFinishableConsumer when the file
                    is completely transferred.
                  - L{Deferred} list of control-connection responses.
        """
        s = SenderProtocol()
        r = self._openDataConnection(command, s)
        return (s.connectedDeferred, r)

    def _openDataConnection(self, command, protocol):
        """
        This method returns a DeferredList.
        """
        cmd = Command(command, public=1)

        if self.passive:
            # Hack: use a mutable object to sneak a variable out of the 
            # scope of doPassive
            _mutable = [None]
            def doPassive(response):
                """Connect to the port specified in the response to PASV"""
                host, port = decodeHostPort(response[-1])

                class _Factory(ClientFactory):
                    noisy = 0
                    def buildProtocol(self, ignored):
                        self.protocol.factory = self
                        return self.protocol
                    def clientConnectionFailed(self, connector, reason):
                        self.protocol.connectionFailed()
                f = _Factory()
                f.protocol = protocol
                _mutable[0] = reactor.connectTCP(host, port, f)

            pasvCmd = Command('PASV')
            self.queueCommand(pasvCmd)
            pasvCmd.deferred.addCallback(doPassive).addErrback(self.fail)

            results = [cmd.deferred, pasvCmd.deferred, protocol.deferred]
            d = DeferredList(results, fireOnOneErrback=1)

            # Ensure the connection is always closed
            def close(x, m=_mutable):
                m[0] and m[0].disconnect()
                return x
            d.addBoth(close)

        else:
            # We just place a marker command in the queue, and will fill in
            # the host and port numbers later (see generatePortCommand)
            portCmd = Command('PORT')

            # Ok, now we jump through a few hoops here.
            # This is the problem: a transfer is not to be trusted as complete
            # until we get both the "226 Transfer complete" message on the 
            # control connection, and the data socket is closed.  Thus, we use
            # a DeferredList to make sure we only fire the callback at the 
            # right time.

            portCmd.transferDeferred = protocol.deferred
            portCmd.protocol = protocol
            portCmd.deferred.addErrback(portCmd.transferDeferred.errback)
            self.queueCommand(portCmd)

            # Create dummy functions for the next callback to call.
            # These will also be replaced with real functions in 
            # generatePortCommand.
            portCmd.loseConnection = lambda result: result
            portCmd.fail = lambda error: error
            
            # Ensure that the connection always gets closed
            cmd.deferred.addErrback(lambda e, pc=portCmd: pc.fail(e) or e)

            results = [cmd.deferred, portCmd.deferred, portCmd.transferDeferred]
            d = DeferredList(results, fireOnOneErrback=1)
                              
        self.queueCommand(cmd)
        return d

    def generatePortCommand(self, portCmd):
        """(Private) Generates the text of a given PORT command"""

        # The problem is that we don't create the listening port until we need
        # it for various reasons, and so we have to muck about to figure out
        # what interface and port it's listening on, and then finally we can
        # create the text of the PORT command to send to the FTP server.

        # FIXME: This method is far too ugly.

        # FIXME: The best solution is probably to only create the data port
        #        once per Client, and just recycle it for each new download.
        #        This should be ok, because we don't pipeline commands.
        
        # Start listening on a port
        factory = DataPortFactory()
        factory.protocol = portCmd.protocol
        listener = reactor.listenTCP(0, factory)
        factory.port = listener

        # Ensure we close the listening port if something goes wrong
        def listenerFail(error, listener=listener):
            if listener.connected:
                listener.loseConnection()
            return error
        portCmd.fail = listenerFail

        # Construct crufty FTP magic numbers that represent host & port
        host = self.transport.getHost()[1]
        port = listener.getHost()[2]
        numbers = string.split(host, '.') + [str(port >> 8), str(port % 256)]
        portCmd.text = 'PORT ' + string.join(numbers,',')

    def escapePath(self, path):
        """Returns a FTP escaped path (replace newlines with nulls)"""
        # Escape newline characters
        return string.replace(path, '\n', '\0')

    def retrieveFile(self, path, protocol):
        """Retrieve a file from the given path

        This method issues the 'RETR' FTP command.
        
        The file is fed into the given Protocol instance.  The data connection
        will be passive if self.passive is set.

        @param path: path to file that you wish to receive.
        @param protocol: a L{Protocol} instance.

        @returns: L{Deferred}
        """
        return self.receiveFromConnection('RETR ' + self.escapePath(path), protocol)

    retr = retrieveFile

    def storeFile(self, path):
        """Store a file at the given path.

        This method issues the 'STOR' FTP command.

        @returns: A tuple of two L{Deferred}s:
                  - L{Deferred} L{IFinishableConsumer}. You must call
                    the C{finish} method on the IFinishableConsumer when the file
                    is completely transferred.
                  - L{Deferred} list of control-connection responses.
        """
        
        return self.sendToConnection('STOR ' + self.escapePath(path))

    stor = storeFile
        
    def list(self, path, protocol):
        """Retrieve a file listing into the given protocol instance.

        This method issues the 'LIST' FTP command.

        @param path: path to get a file listing for.
        @param protocol: a L{Protocol} instance, probably a
            L{FileListProtocol} instance.  It can cope with most common file
            listing formats.

        @returns: L{Deferred}
        """
        if path is None:
            path = ''
        return self.receiveFromConnection('LIST ' + self.escapePath(path), protocol)
        
    def nlst(self, path, protocol):
        """Retrieve a short file listing into the given protocol instance.

        This method issues the 'NLST' FTP command.
        
        NLST (should) return a list of filenames, one per line.

        @param path: path to get short file listing for.
        @param protocol: a L{Protocol} instance.
        """
        if path is None:
            path = ''
        return self.receiveFromConnection('NLST ' + self.escapePath(path), protocol)

    def queueStringCommand(self, command, public=1):
        """Queues a string to be issued as an FTP command
        
        @param command: string of an FTP command to queue
        @param public: a flag intended for internal use by Client.  Don't
            change it unless you know what you're doing.
        
        @returns: a L{Deferred} that will be called when the response to the
        command has been received.
        """
        ftpCommand = Command(command, public)
        self.queueCommand(ftpCommand)
        return ftpCommand.deferred

    def cwd(self, path):
        """Issues the CWD (Change Working Directory) command.

        @returns: a L{Deferred} that will be called when done.
        """
        return self.queueStringCommand('CWD ' + self.escapePath(path))

    def cdup(self):
        """Issues the CDUP (Change Directory UP) command.

        @returns: a L{Deferred} that will be called when done.
        """
        return self.queueStringCommand('CDUP')

    def pwd(self):
        """Issues the PWD (Print Working Directory) command.

        @returns: a L{Deferred} that will be called when done.  It is up to the 
            caller to interpret the response, but the L{parsePWDResponse} method
            in this module should work.
        """
        return self.queueStringCommand('PWD')

    def quit(self):
        """Issues the QUIT command."""
        return self.queueStringCommand('QUIT')
    
    def lineReceived(self, line):
        """(Private) Parses the response messages from the FTP server."""
        # Add this line to the current response
        if self.debug:
            log.msg('--> %s' % line)
        line = string.rstrip(line)
        self.response.append(line)

        code = line[0:3]
        
        # Bail out if this isn't the last line of a response
        # The last line of response starts with 3 digits followed by a space
        codeIsValid = len(filter(lambda c: c in '0123456789', code)) == 3
        if not (codeIsValid and line[3] == ' '):
            return

        # Ignore marks
        if code[0] == '1':
            return

        # Check that we were expecting a response
        if self.nextDeferred is None:
            self.fail(UnexpectedResponse(self.response))
            return

        # Reset the response
        response = self.response
        self.response = []

        # Look for a success or error code, and call the appropriate callback
        if code[0] in ('2', '3'):
            # Success
            self.nextDeferred.callback(response)
        elif code[0] in ('4', '5'):
            # Failure
            self.nextDeferred.errback(Failure(CommandFailed(response)))
        else:
            # This shouldn't happen unless something screwed up.
            log.msg('Server sent invalid response code %s' % (code,))
            self.nextDeferred.errback(Failure(BadResponse(response)))
            
        # Run the next command
        self.sendNextCommand()
        

class FileListProtocol(basic.LineReceiver):
    """Parser for standard FTP file listings
    
    This is the evil required to match::

        -rw-r--r--   1 root     other        531 Jan 29 03:26 README

    If you need different evil for a wacky FTP server, you can override this.

    It populates the instance attribute self.files, which is a list containing
    dicts with the following keys (examples from the above line):
        - filetype: e.g. 'd' for directories, or '-' for an ordinary file
        - perms:    e.g. 'rw-r--r--'
        - owner:    e.g. 'root'
        - group:    e.g. 'other'
        - size:     e.g. 531
        - date:     e.g. 'Jan 29 03:26'
        - filename: e.g. 'README'

    Note that the 'date' value will be formatted differently depending on the
    date.  Check U{http://cr.yp.to/ftp.html} if you really want to try to parse
    it.

    @ivar files: list of dicts describing the files in this listing
    """
    fileLinePattern = re.compile(
        r'^(?P<filetype>.)(?P<perms>.{9})\s+\d*\s*'
        r'(?P<owner>\S+)\s+(?P<group>\S+)\s+(?P<size>\d+)\s+'
        r'(?P<date>... .. ..:..)\s+(?P<filename>.*?)\r?$'
    )
    delimiter = '\n'

    def __init__(self):
        self.files = []

    def lineReceived(self, line):
        match = self.fileLinePattern.match(line)
        if match:
            dict = match.groupdict()
            dict['size'] = int(dict['size'])
            self.files.append(dict)

def parsePWDResponse(response):
    """Returns the path from a response to a PWD command.

    Responses typically look like::

        257 "/home/andrew" is current directory.

    For this example, I will return C{'/home/andrew'}.

    If I can't find the path, I return C{None}.
    """
    match = re.search('".*"', response)
    if match:
        return match.groups()[0]
    else:
        return None

FTPClient = Client
FTPFileListProtocol = FileListProtocol
FTPDataPortFactory = DataPortFactory
FTPCommand = Command
FTPError = Error
