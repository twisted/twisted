# -*- test-case-name: twisted.test.test_ftp2 -*-
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
import zope.interface as zi

# Twisted Imports
from twisted.internet import abstract, reactor, protocol, error, defer
from twisted.internet.interfaces import IProducer, IConsumer, IProtocol, IFinishableConsumer
from twisted.protocols import basic, policies
from twisted.internet.protocol import ClientFactory, ServerFactory, Protocol, \
                                      ConsumerToProtocolAdapter

from twisted import application, internet, python
from twisted.python import failure, log, components

from twisted.cred import error as cred_error, portal, checkers, credentials


#-- transfer modes ------------------------------

PASV = 1
PORT = 2

ENDLN = str('\015\012')

#-- response codes ------------------------------

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

# -- EXCEPTIONS --------------------------------------

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

class BadCmdSequenceError(Exception):
    """raised when a client sends a series of commands in an illogical sequence"""
    pass


# -- INTERFACES -------------------------------------

class IFTPShell(zi.Interface):
    """An abstraction of the shell commands used by the FTP protocol
    for a given user account
    """

    def mapCPathToSPath(path):
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

    def pwd():
        """ Print working directory command
        """
        pass

    def cwd(path):
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

    def cdup():
        """changes to the parent of the current working directory
        """
        pass

    def size(path):
        """returns the size of the file specified by path in bytes
        """
        pass

    def mkd(path):
        """ This command causes the directory specified in the pathname
        to be created as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative).

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def rmd(path):
        """ This command causes the directory specified in the pathname
        to be removed as a directory (if the pathname is absolute)
        or as a subdirectory of the current working directory (if
        the pathname is relative). 

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def dele(path):
        """This command causes the file specified in the pathname to be
        deleted at the server site. 

        @param path: the path you're interested in
        @type path: string
        """
        pass

    def list(path):
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

    def nlst(path):
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

    def retr(path):
        """ This command causes the server-DTP to transfer a copy of the
        file, specified in the pathname, to the server- or user-DTP
        at the other end of the data connection.  The status and
        contents of the file at the server site shall be unaffected.

        @return: a tuple of (fp, size) where fp is an opened file-like object 
        to the data requested and size is the size, in bytes, of fp
        """
        pass

    def stor(params):
        """This command causes the server-DTP to accept the data
        transferred via the data connection and to store the data as
        a file at the server site.  If the file specified in the
        pathname exists at the server site, then its contents shall
        be replaced by the data being transferred.  A new file is
        created at the server site if the file specified in the
        pathname does not already exist.
        """
        pass

    def mdtm(path):
        """get the date and time for path
        @param path: the path you're interested in
        @type path: string
        @return: the date of path in the form of %Y%m%d%H%M%S
        @rtype: string
        """
        pass


# -- TEH PROTOCOL -----------------------------------

class FTP(object, basic.LineReceiver):
    """Protocol Interpreter for the File Transfer Protocol
    """
    user = shell = None
    binary = True
    reTelnetChars = re.compile(r'(\\x[0-9a-f]{2}){1,}')
    
    def connectionMade(self):
        self.reply(WELCOME_MSG)

    def reply(self, key, s=''):                                               
        """format a RESPONSE and send it out over the wire"""
        if string.find(RESPONSE[key], '%s') > -1:
            log.debug(RESPONSE[key] % s + ENDLN)
            self.transport.write(RESPONSE[key] % s + ENDLN)
        else:
            log.debug(RESPONSE[key] + ENDLN)
            self.transport.write(RESPONSE[key] + ENDLN)

    def lineReceived(self, line):
        line = string.strip(line)
        line = self.reTelnetChars.sub('', line)  # clean up '\xff\xf4\xff' nonsense
        line = line.encode() 
        try:
            cmdargs = line.split(' ',1)
            self.processCommand(*cmdargs)
        except CmdSyntaxError, (e,):
            self.reply(SYNTAX_ERR, string.upper(cmdargs[0]))
        except CmdArgSyntaxError, (e,):
            self.reply(SYNTAX_ERR_IN_ARGS, e)
        except BadCmdSequenceError, (e,): 
            self.reply(BAD_CMD_SEQ, e)
        except Exception, e:
            print e

    def processCommand(self, cmd, *args):
        if not self.shell and cmd not in ['USER', 'PASS']:
            self.reply(NOT_LOGGED_IN)
            return

        method = getattr(self, "ftp_%s" % cmd, None)                            # try to find the method in this class
        log.debug('FTP.processCommand: method = %s' % method)
        if method:
            return method(*args)                                                
        raise CmdNotImplementedError(cmd)                 # if we didn't find cmd, raise an error and alert client


    def ftp_USER(self, arg=''):
        if arg=='':
            raise CmdSyntaxError('no parameters')
        self.user = string.split(arg)[0]
        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.reply(GUEST_NAME_OK_NEED_EMAIL)
        else:
            self.reply(USR_NAME_OK_NEED_PASS, self.user)
    
    def ftp_PASS(self, arg=''):
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

        if arg == '':
            raise CmdArgSyntaxError('you must specify a password with PASS')
        
        self.passwd = arg.split()[0] 

        def _cbAnonLogin((interface, avatar, logout)):
            # if this is an anonymous login
            assert IFTPShell.providedBy(avatar)
            self.shell = avatar
            self.logout = logout
            self.reply(GUEST_LOGGED_IN_PROCEED)

        def _cbLogin((interface, avatar, logout)):
            # sets up authorized user login avatar
            assert IFTPShell.providedBy(avatar)
            self.shell = avatar
            self.logout = logout
            self.reply(USR_LOGGED_IN_PROCEED)

        def _ebLogin(err):
            r = err.trap(cred_error.UnauthorizedLogin, TLDNotSetInRealmError)
            if r == TLDNotSetInRealmError:
                log.debug(err.getErrorMessage())
                self.reply(REQ_ACTN_NOT_TAKEN, 'internal server error')
                self.transport.loseConnection()
            else:
                self.reply(AUTH_FAILURE, '')

        if self.factory.allowAnonymous and self.user == self.factory.userAnonymous:
            self.passwd = arg
            if self.portal:
                self.portal.login(credentials.Anonymous(), None, IFTPShell
                                  ).addCallbacks(_cbAnonLogin, _ebLogin)
            else:
                # if cred has been set up correctly, this shouldn't happen
                raise AuthorizationError('internal server error')

        # otherwise this is a user login
        else:
            if self.portal:
                self.portal.login(credentials.UsernamePassword(self.user, self.passwd), None, IFTPShell
                                  ).addCallbacks(_cbLogin, _ebLogin)
            else:
                raise AuthorizationError('internal server error')


    def ftp_TYPE(self, type):
        pass

    def ftp_SYST(self, arg):
        pass

    def ftp_LIST(self, arg):
        pass

    def ftp_SIZE(self, arg):
        pass

    def ftp_MDTM(self, arg):
        pass

    def ftp_PWD(self, arg):
        pass

    def ftp_PASV(self):
        pass

    def ftp_PORT(self, arg):
        pass

    def ftp_CWD(self, arg):
        pass

    def ftp_CDUP(self):
        pass

    def ftp_RETR(self, arg):
        pass

    def ftp_STRU(self, arg):
        pass

    def ftp_MODE(self, arg):
        pass
    
    def ftp_QUIT(self, arg):
        pass
    

class FTPFactory(protocol.Factory):
    protocol = FTP


# -- CRED ----------------------------------------------    

class FTPRealm:
    zi.implements(portal.IRealm)
    
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
        if IFTPShell in interfaces:
            if self.tld is None:
                raise TLDNotSetInRealmError("you must set FTPRealm's tld to a non-None value before creating avatars!!!")
            avatar = FTPAnonymousShell(user=self.user, tld=self.tld)
            avatar.clientwd = self.clientwd
            avatar.logout = self.logout
            return IFTPShell, avatar, avatar.logout
        raise NotImplementedError("Only IFTPShell interface is supported by this realm")

# do we need this?
components.backwardsCompatImplements(FTPRealm)

