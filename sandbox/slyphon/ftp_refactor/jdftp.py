# originally written by phed 
# FTPClient written by spiv
# server and client refactor by slyphon (Jonathan D. Simms)

# System Imports
import os
import time
import string
import types
import re
from cStringIO import StringIO
from math import floor

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic, policies
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter

from twisted import application
from twisted import internet
from twisted.internet import defer
from twisted.python import failure
from twisted.python import log, components

from twisted.cred import error, portal, checkers, credentials

# constants

MODULE_DEBUG = True

PASV = 1
PORT = 2

ENDLN = str('\015\012')

# response codes

RESTART_MARKER_REPLY                    = 100
SERVICE_READY_IN_N_MINUTES              = 120
DATA_CNX_ALREADY_OPEN_START_XFR         = 125
FILE_STATUS_OK_OPEN_DATA_CNX            = 150

CMD_OK                                  = 200.1
TYPE_SET_OK                             = 200.2
ENTERING_PORT_MODE                      = 200.3
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
NEED_ACCT_FOR_STOR                      = 532
FILE_NOT_FOUND                          = 550.1     # no such file or directory
PERMISSION_DENIED                       = 550.2     # permission denied
ANON_USER_DENIED                        = 550.3     # anonymous users can't alter filesystem
IS_NOT_A_DIR                            = 550.4     # rmd called on a path that is not a directory
REQ_ACTN_NOT_TAKEN                      = 550.5
PAGE_TYPE_UNK                           = 551
EXCEEDED_STORAGE_ALLOC                  = 552
FILENAME_NOT_ALLOWED                    = 553


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
    WELCOME_MSG:                        '220 Welcome, twisted.ftp at your service.',
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

# -- Utility Functions --

def debugDeferred(self, *_):
    log.debug(_)
        
# -- Custom Exceptions --

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
    '''raised when RMD is called on a path that isn't a directory
    '''
    pass

class OperationFailedError(Exception):
    '''raised when a command like rmd or mkdir fails for a reason other than permissions errors
    '''
    pass

class CmdSyntaxError(Exception):
    pass

class CmdArgSyntaxError(Exception):
    pass

class CmdNotImplementedError(Exception):
    '''raised when an unimplemented command is given to the server
    '''
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
    '''thrown when a client other than the one we opened this 
    DTP connection for attempts to connect, or a client attempts to
    get us to connect to an ip that differs from the one where the 
    request came from'''
    pass

class PathBelowTLDError(Exception):
    pass

class ClientDisconnectError(Exception):
    pass

class BadCmdSequenceError(Exception):
    '''raised when a client sends a series of commands in an illogical sequence'''
    pass

class AuthorizationError(Exception):
    '''raised when client authentication fails'''
    pass

# -- DTP Protocol --

class DTPFileSender(basic.FileSender):
    def stopProducing(self):
        if self.deferred:
            self.deferred.errback(ClientDisconnectError())
            self.deferred = None


def _getFPName(fp):
    '''returns a file object's name attr if it has one,
    otherwise it returns "name"
    '''
    if hasattr(fp, 'name'):
        return fp.name
    return 'file'   # stringIO objects have no .name attr

class DTP(protocol.Protocol):
    '''The Data Transfer Protocol for this FTP-PI instance
    all dtp_* methods return a deferred
    '''
    def connectionMade(self):
        """Will start an transfer, if one is queued up, 
        when the client connects"""
        peer = self.transport.getPeer()
        log.debug('got a DTP connection %s:%s' % (peer[1],peer[2]))

        d, self.factory.deferred = self.factory.deferred, defer.Deferred()

        if self.factory.peerCheck and peer[1] != self.pi.peerHost[1]:
            # DANGER Will Robinson! Bailing!
            log.debug('dtp ip did not match ftp ip')
            d.errback(BogusClientError("%s != %s" % (peer[1], self.pi.peerHost[1])))   
            return

        log.debug('firing dtpFactory deferred')
        d.callback(None)

    #TODO: need to test this. taken directly from the pop3 code
    #      so i don't know if the commented-out chunk on the right
    #      is necessary
    def transformChunk(self, chunk):
        return chunk.replace('\n', '\r\n') #.replace('\r\n.', '\r\n..')

    def dtp_RETR(self, fp): # RETR = sendFile
        '''ssnds a file object out the wire'''
        filename = _getFPName(fp)

        log.debug('sendfile sending %s' % filename)

        fs = DTPFileSender()
        if not self.pi.binary:
            transform = self.transformChunk
        else:
            transform = None
        return fs.beginFileTransfer(fp, self.transport, transform
                ).addCallback(self.finishedFileTransfer
                )

    def finishedFileTransfer(self, *arg):
        self.transport.loseConnection()
        self.pi.reply(TXFR_COMPLETE_OK)


#TODO:  implement timeout functionality for this factory
#       after the factories' creation, it should wait for n minutes
#       before giving up. this wouldn't work in the protocol because
#       the protocol waits for n minutes of idle time and for some reason
#       the TimeoutMixin doesn't seem to work in this scenario
#
#       the factory times *waiting* for a connection (to create a protocol)
class DTPFactory(protocol.ServerFactory): 
    # -- configuration variables --
    peerCheck = True
    protocol = DTP

    # -- class variables --
    def __init__(self, pi, peerHost):
        self.pi = pi                        # the protocol interpreter that is using this factory
        self.peerHost = peerHost            # the from FTP.transport.getHost()
        self.deferred = defer.Deferred()    # deferred will fire when instance is connected

    def buildProtocol(self, addr):
        self.cancelTimeout()
        if self.pi.dtpInstance:   # only create one instance
            return 
        p = protocol.ServerFactory.buildProtocol(self, addr)      # like in __init__ of a base-class
        p.factory = self
        p.pi = self.pi
        self.pi.dtpInstance = p
        return p

    def stopFactory(self):
        self.pi.cleanupDTP()

    def timeoutFactory(self):
        log.msg('timed out waiting for DTP connection')
        if self.deferred:
            d, self.deferred = self.deferred, None 
            d.errback(defer.TimeoutError())
        self.stopFactory()

    def cancelTimeout(self):
        self.delayedCall.cancel()

    def setTimeout(self, seconds):
        self.delayedCall = reactor.callLater(seconds, self.timeoutFactory)

# -- FTP-PI (Protocol Interpreter) --


def cleanPath(params):
    # cleanup backslashes and multiple foreslashes
    if params:
        params = re.sub(r'[\\]{2,}?', '/', params)
        params = re.sub(r'[/]{2,}?','/', params)
    return params

class FTP(basic.LineReceiver, policies.TimeoutMixin):      
    # FTP is a bit of a misonmer, as this is the PI - Protocol Interpreter
    blockingCommands = ['RETR', 'STOR', 'LIST', 'PORT']

    # how long the DTP waits for a connection
    dtpTimeout = 13
    
    def __init__(self):
        self.portal      = None
        self.shell       = None     # the avatar
        self.dtpFactory  = None     # generates a single DTP for this session
        self.dtpInstance = None     # a DTP protocol instance
        self.dtpPort     = None     # the port that the DTPFactory is listening on
        self.user        = None     # the username of the client connected 
        self.peerHost    = None     # the (type,ip,port) of the client
        self.dtpTxfrMode = None     # PASV or PORT, no default
        self.blocked     = None     # a command queue for pipelining 
        self.binary      = None     # binary transfers? False implies ASCII
        self.dtpHostPort = None     # client address/port to connect to on PORT command
        self.timeOut     = None     # how much idleness we can stand before leaving
    
    def connectionMade(self):
        log.debug('ftp-pi connectionMade')
        self.reply(WELCOME_MSG)
        self.peerHost = self.transport.getPeer()
        self.setTimeout(self.timeOut)
        self.__testingautologin()

    def __testingautologin(self):
        import warnings; warnings.warn('''

            --> DEBUGGING CODE ACTIVE!!! <--
''')
        self.timeOut = 10
        lr = self.lineReceived
        lr('USER anonymous')
        lr('PASS f@d.com')
        lr('PASV')
        lr('LIST')
        lr('RETR .vim/vimrc')
        lr('RETR Session.vim')

    def connectionLost(self, reason):
        log.msg("Oops! lost connection\n %s" % reason)
        # if we have a DTP protocol instance running and
        # we lose connection to the client's PI, kill the 
        # DTP connection and close the port
        if self.dtpFactory:
            self.cleanupDTP()
        self.setTimeout(None)

    def timeoutConnection(self):
        log.msg('FTP timed out')
        self.transport.loseConnection()
        if self.dtpFactory.deferred:
            d, self.dtpFactory.deferred = self.dtpFactory.deferred, None
            d.errback(FTPTimeoutError('cleaning up dtp!'))
        
    def lineReceived(self, line):
        "Process the input from the client"
        self.resetTimeout()
        line = string.strip(line)
        log.debug(repr(line))
        line = line.encode() 
        try:
            #return self.processCommand(*line.split())
            self.processCommand(*line.split())
        except CmdSyntaxError, (e,):
            self.reply(SYNTAX_ERR, string.upper(command))
        except CmdArgSyntaxError, (e,):
            log.err(e)
            self.reply(SYNTAX_ERR_IN_ARGS, e)
        except AnonUserDeniedError, (e,):
            log.err(e)
            self.reply(ANON_USER_DENIED, e)
        except CmdNotImplementedError, (e,):
            log.err(e)
            self.reply(CMD_NOT_IMPLMNTD, e)
        except BadCmdSequenceError, (e,): 
            log.err(e)
            self.reply(BAD_CMD_SEQ, e)
        except AuthorizationError, (e,):
            log.err(e)
            self.reply(AUTH_FAILURE, 'internal server error')
        except FileNotFoundError, (e,):
            self.reply(FILE_NOT_FOUND, e)
        except PathBelowTLDError, (e,):
            self.reply(PERMISSION_DENIED, e)
        except (ValueError, AttributeError, TypeError), (e,):
            log.err(e)
            self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')

    def processCommand(self, cmd, *args):
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
            if not self.dtpInstance:                                            # if no one has connected yet
                # a bit hackish, but manually blocks this command 
                # until we've set up the DTP protocol instance
                assert self.blocked == None                                     # we should not be blocked if we haven't run any DTP commands yet
                self.blocked = [(cmd,args)]                                     # add item to queue and start blocking
                log.debug('during dtp setup, blocked = %s' % self.blocked)
                return
        method = getattr(self, "ftp_%s" % cmd, None)                            # try to find the method in this class
        if method:
            return method(*args)                                                
        raise CmdNotImplementedError(cmd)                 # if we didn't find cmd, raise an error and alert client
        log.debug("SOMETHING IS SCREWY")

    def _unblock(self, *_):
        log.debug('_unblock running')                                           # unblock commands
        commands = self.blocked                                                 
        self.blocked = None                                                     # reset blocked to allow new commands
        while commands and self.blocked is None:                                # while no other method has set self.blocked
            cmd, args = commands.pop(0)                                         # pop a command off the queue
            self.processCommand(cmd, *args)                                     # and process it
        if self.blocked is not None:                                            # if someone has blocked during the time we were processing
            self.blocked.extend(commands)                                       # add our commands that we dequeued back into the queue

    def reply(self, key, s = ''):                                               
        '''format a RESPONSE and send it out over the wire'''
        if string.find(RESPONSE[key], '%s') > -1:
            log.debug(RESPONSE[key] % s + ENDLN)
            self.transport.write(RESPONSE[key] % s + ENDLN)
        else:
            log.debug(RESPONSE[key] + ENDLN)
            self.transport.write(RESPONSE[key] + ENDLN)

    def _createDTP(self):
        self.setTimeout(None)     # don't timeOut when setting up DTP
        log.debug('_createDTP')
        if not self.dtpFactory:
            phost = self.transport.getPeer()[1]
            self.dtpFactory = DTPFactory(pi=self, peerHost=phost)

        if self.dtpTxfrMode == PASV:
            self.dtpPort = reactor.listenTCP(0, self.dtpFactory)   
        elif self.dtpHostPort: 
            self.dtpPort = reactor.connectTCP(host=self.dtpHostPort[1], 
                                              port=self.dtpHostPort[2])
        else:
            log.err('SOMETHING IS SCREWY: _createDTP')

        d = self.dtpFactory.deferred        
        d.addCallback(debugDeferred, 'dtpFactory deferred')
        d.addCallback(self._unblock)                            # VERY IMPORTANT: call _unblock when client connects
        d.addErrback(self._ebDTP)

    def _ebDTP(self, error):
        self.setTimeout(self.timeOut)               # restart timeOut clock after DTP returns
        log.err(error)
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
        # TODO: find out if this is correct pipelining behavior
        #       if any error happens, all previously pipelined commands
        #       are junked
        self.blocked = None                         
        
    def cleanupDTP(self):
        """call when DTP connection exits
        """
        log.debug('cleanupDTP')
        if hasattr(self.dtpPort, 'connected'):
            if self.dtpPort.connected:
                self.dtpPort.loseConnection()
            if hasattr(self.dtpPort.transport, 'socket'):
                log.debug('transport has socket, running stopListening()')
                self.dtpPort.stopListening()
            self.dtpFactory = None
            self.dtpInstance = None
            self.dtpPort = None

    def _doDTPCommand(self, cmd, arg):
        self.setTimeout(None)               # don't Time out when waiting for DTP Connection
        if self.blocked is None:
            self.blocked = []
        try:
            f = getattr(self.dtpInstance, "dtp_%s" % cmd, None)
        except AttributeError, e:
            log.err('SOMETHING IS SCREWY IN _doDTPCommand')
            raise e
        else:
            self.dtpFactory.setTimeout(self.dtpTimeout)
            f(arg).addCallback(debugDeferred, 'deferred returned to _doDTPCommand'
                ).addCallback(self._cbDTPCommand
                ).addCallback(self._unblock
                ).addErrback(self._ebDTP)

    def _cbDTPCommand(self, arg):
        log.debug("DTP Command success: %s" % arg)
        self.setTimeout(self.timeOut)               # restart timeOut clock after DTP returns

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
        log.debug('ftp_USER params: %s' % params)
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)

    # TODO: add max auth try before timeout from ip...

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
            raise BadCmdSequenceError('USER required before PASS')

        log.debug('ftp_PASS params: %s' % params)

        
        self.passwd = params.split()[0]        # parse password 

        # if this is an anonymous login
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.passwd = params
            if self.portal:
                self.portal.login(
                        credentials.Anonymous(), 
                        None, 
                        IFTPShell
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
                        IFTPShell
                    ).addCallbacks(self._cbLogin, self.ebLogin
                    )
            else:
                raise AuthorizationError('internal server error')

    def _cbAnonLogin(self, (interface, avatar, logout)):
        '''sets up anonymous login avatar'''
        assert interface is IFTPShell
        peer = self.transport.getPeer()
#       log.debug("Anonymous login from %s:%s" % (peer[1], peer[2]))
        self.shell = avatar
        self.logout = logout
        self.reply(GUEST_LOGGED_IN_PROCEED)

    def _cbLogin(self, (interface, avatar, logout)):
        '''sets up authorized user login avatar'''
        assert interface is IFTPShell
        self.shell = avatar
        self.logout = logout
        self.reply(USR_LOGGED_IN_PROCEED)

    def _ebLogin(self, failure):
        failure.trap(error.UnauthorizedLogin)
        self.reply(AUTH_FAILURE, '')

    def ftp_TYPE(self, *params):
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
        log.debug('ftp_LIST: %s' % params)
        if params == "-a": params = ''  # bug in konqueror
        if params == "-aL": params = '' # bug in gFTP 2.0.15

        sioObj = self.shell.list(cleanPath(params))    # returns a StringIO object
        if self.dtpInstance.connected:
            self.reply(DATA_CNX_ALREADY_OPEN_START_XFR)
        else:
            self.reply(FILE_STATUS_OK_OPEN_DATA_CNX)
        self._doDTPCommand('RETR', sioObj)
 
    def ftp_PWD(self, params=''):
        """ Print working directory command
        """
        self.reply(PWD_REPLY, self.shell.pwd())
    

    def ftp_PASV(self, *_):
        """Request for a passive connection

        reply is in format 227 =h1,h2,h3,h4,p1,p2

        from the rfc:
            This command requests the server-DTP to "listen" on a data
            port (which is not its default data port) and to wait for a
            connection rather than initiate one upon receipt of a
            transfer command.  The response to this command includes the
            host and port address this server is listening on.
        """
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

    def decodeHostPort(self, line):
        """Decode an FTP response specifying a host and port.
        
        see RFC sec. 4.1.2 "PASV"

        @returns: a 2-tuple of (host, port).
        """
        abcdef = re.sub('[^0-9, ]', '', line[4:])
        a, b, c, d, e, f = map(str.strip, abcdef.split(','))
        host = "%s.%s.%s.%s" % (a, b, c, d)
        port = (int(e)<<8) + int(f)
        return (host, port)


    def ftp_PORT(self, params):
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

    def ftp_CDUP(self, params):
        self.shell.cdup()
        self.reply(REQ_FILE_ACTN_COMPLETED_OK)

    def ftp_RETR(self, params):
        if self.dtpTxfrMode is None:
            raise BadCmdSequenceError('must send PORT or PASV before RETR')
        fp = self.shell.retr(cleanPath(params))
        self._doDTPCommand('RETR', fp)

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


class FTPFactory(protocol.Factory):
    protocol = FTP
    allowAnonymous = True
    userAnonymous = 'anonymous'
    timeOut = 300

    def __init__(self, portal=None):
        self.portal = portal

    def buildProtocol(self, addr):
        pi            = protocol.Factory.buildProtocol(self, addr)
        pi.protocol   = self.protocol
        pi.portal     = self.portal
        pi.timeOut    = self.timeOut
        return pi

# -- Cred Objects --

class IFTPShell(components.Interface):
    """An abstraction of the shell commands used by the FTP protocol
    for a given user account
    """

    def buildFullPath(self, path):
        """converts a specified path relative to the user's top level directory
        into a path in the filesystem representation

        example: if the user's tld is /home/foo and there's a file in the filesystem
        /home/foo/bar/spam.tar.gz the user would specify path /bar/spam.tar.gz in the 
        ftp command, and this function would translate it into /home/foo/bar/spam.tar.gz
        """
        pass

    def pwd(self):
        """ Print working directory command
        """
        pass

    def cwd(self, path):
        """Change working directory

        should throw a FileNotFound exception on failure

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
        """return a StringIO object containing the directory listing to
        be sent to the client via the DTP

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
        """
        pass

    def retr(self, path):
        """ This command causes the server-DTP to transfer a copy of the
        file, specified in the pathname, to the server- or user-DTP
        at the other end of the data connection.  The status and
        contents of the file at the server site shall be unaffected.

        returns an opened file-like object to the data requested
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


class FTPAnonymousShell(object):
    __implements__ = (IFTPShell,)

    def __init__(self):
        self.user     = None         # user name
        self.clientwd = None
        self.tld      = None
        self.debug    = True

    # basically, i'm thinking of the paths as a list of path elements
    #
    # some terminology:
    # client absolute path = an absolute path minus the tld
    # server absolute path = a full absolute path on the filesystem
    # client relative path = a path relative to the client's working directory

    def pwd(self):
        return self.clientwd

    def myjoin(self, lpath, rpath):
        if lpath and lpath[-1] == os.sep:
            lpath = lpath[:-1]
        if rpath and rpath[0] == os.sep:
            rpath = rpath[1:]
        return "%s/%s" % (lpath, rpath)

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
        class _:
            def __init__(self, cpath, spath):
                self.clientPath = cpath
                self.serverPath = spath
        return _(ncpath, nspath)
 
    def cwd(self, path):
        mapped = self.mapCPathToSPath(path)
        if os.path.exists(mapped.serverPath) and os.path.isdir(mapped.serverPath):
            self.clientwd = mapped.clientPath
        else:
            raise FileNotFoundError(mapped.clientPath)
       
    def cdup(self):
        self.cwd('..')

#    def size(self, path):
#        # is this specified in the RFC?
#        """"""
#        npath = self.buildFullPath(path)
#        if not os.path.isfile(npath):
#            raise FileNotFoundError(path)
#        return os.path.getsize(npath)

    def dele(self, path):
        raise AnonUserDeniedError()
        
    def mkd(self, path):
        raise AnonUserDeniedError()
        
    def rmd(self, path):
        raise AnonUserDeniedError()
 
    def retr(self, path):
        mapped = self.mapCPathToSPath(path)
        if not os.path.isfile(mapped.serverPath):
            raise FileNotFoundError(mapped.clientPath)
#        if not os.access(npath, os.O_RDONLY):
#            raise PermissionDeniedError(npath)
        # TODO: need to do some kind of permissions checking here
        return file(mapped.serverPath, 'rb')

    def stor(self, params):
        raise AnonUserDeniedError()

    def list(self, path):
        spath = self.mapCPathToSPath(path).serverPath
        alist = os.listdir(spath)
        s = ''
        for a in alist:
            ts = a
            ff = os.path.join(path, ts) # the full filename
            try:
                # TODO: FIX THIS ALREADY!!!
                #
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
        sio = StringIO(s)
        sio.seek(0)         # rewind the file position to the beginning
        return sio          # a file-like object to send down the wire

    def nlist(self, path):
        pass


class FTPRealm:
    __implements__ = (portal.IRealm,)
    ANONYMOUS_DIR = '/home/jonathan'

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IFTPShell in interfaces:
            if avatarId == checkers.ANONYMOUS:
                avatar = FTPAnonymousShell()
                avatar.tld = self.ANONYMOUS_DIR
                avatar.clientwd = '/'
                avatar.user = 'anonymous'
                avatar.logout = None
            return IFTPShell, avatar, avatar.logout
        raise NotImplementedError("Only IFTPShell interface is supported by this realm")




