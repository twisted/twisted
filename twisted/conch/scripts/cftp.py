# -*- test-case-name: twisted.conch.test.test_sftp -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# $Id: cftp.py,v 1.65 2004/03/11 00:29:14 z3p Exp $

#""" Implementation module for the `cftp` command.
#"""
from twisted.conch.client import agent, connect, default, options
from twisted.conch.error import ConchError
from twisted.conch.ssh import connection, common
from twisted.conch.ssh import channel, filetransfer
from twisted.protocols import basic
from twisted.internet import reactor, stdio, defer, abstract, fdesc
from twisted.python import log, usage, failure

import os, sys, getpass, struct, tty, fcntl, base64, signal, stat, errno
import fnmatch

class ClientOptions(options.ConchOptions):
    
    synopsis = """Usage:   cftp [options] [user@]host
         cftp [options] [user@]host[:dir[/]]
         cftp [options] [user@]host[:file [localfile]]
"""
    
    optParameters = options.ConchOptions.optParameters + \
                    [
                    ['buffersize', 'B', 32768, 'Size of the buffer to use for sending/receiving.'],
                    ['batchfile', 'b', None, 'File to read commands from, or \'-\' for stdin.'],
                    ['requests', 'R', 5, 'Number of requests to make before waiting for a reply.'],
                    ['subsystem', 's', 'sftp', 'Subsystem/server program to connect to.']]

    def parseArgs(self, host, localPath=None):
        self['remotePath'] = ''
        if ':' in host:
            host, self['remotePath'] = host.split(':', 1)
            self['remotePath'].rstrip('/')
        self['host'] = host
        self['localPath'] = localPath 

def run():
    args = sys.argv[1:]
    if '-l' in args: # cvs is an idiot
        i = args.index('-l')
        args = args[i:i+2]+args
        del args[i+2:i+4]
    options = ClientOptions()
    try:
        options.parseOptions(args)
    except usage.UsageError, u:
        print 'ERROR: %s' % u
        sys.exit(1)
    if options['log']:
        realout = sys.stdout
        log.startLogging(sys.stderr)
        sys.stdout = realout
    else:
        log.discardLogs()
    doConnect(options)
    reactor.run()

def handleError():
    from twisted.python import failure
    global exitStatus
    exitStatus = 2
    try:
        reactor.stop()
    except: pass
    log.err(failure.Failure())
    raise

def doConnect(options):
#    log.deferr = handleError # HACK
    if '@' in options['host']:
        options['user'], options['host'] = options['host'].split('@',1)
    host = options['host']
    if not options['user']:
        options['user'] = getpass.getuser() 
    if not options['port']:
        options['port'] = 22
    else:
        options['port'] = int(options['port'])
    host = options['host']
    port = options['port']
    conn = SSHConnection()
    conn.options = options
    vhk = default.verifyHostKey
    uao = default.SSHUserAuthClient(options['user'], options, conn)
    connect.connect(host, port, options, vhk, uao).addErrback(_ebExit)

def _ebExit(f):
    #global exitStatus
    if hasattr(f.value, 'value'):
        s = f.value.value
    else:
        s = str(f)
    print s
    #exitStatus = "conch: exiting with error %s" % f
    try:
        reactor.stop()
    except: pass

def _ignore(*args): pass

class StdioClient(basic.LineReceiver):

    ps = 'cftp> '
    delimiter = '\n'

    def __init__(self, client):
        self.client = client
        self.currentDirectory = ''

    def connectionMade(self):
        self.client.realPath('').addCallback(self._cbSetCurDir)
        self.transport.stopReading()

    def _cbSetCurDir(self, path):
        self.currentDirectory = path
        self.transport.startReading()
        self._newLine()

    def lineReceived(self, line):
        log.msg('got line "%s"' % repr(line))
        line = line.lstrip()
        if not line:
            self._newLine()
            return
        if ' ' in line:
            command, rest = line.split(' ', 1)
            rest = rest.lstrip()
        else:
            command, rest = line, ''
        command = command.upper()
        f = getattr(self, 'cmd_%s' % command, None)
        if f is not None:
            d = defer.maybeDeferred(f, rest)
            d.addCallback(self._cbCommand)
            d.addErrback(self._ebCommand)
        else:
            self._ebCommand(failure.Failure(NotImplementedError(
                "No command called `%s'" % command)))
            self._newLine()

    def _newLine(self):
        self.transport.write(self.ps)

    def _cbCommand(self, result):
        if result is not None:
            self.transport.write(result)
            if not result.endswith('\n'):
                self.transport.write('\n')
        if not self.client.transport.localClosed:
            self._newLine()

    def _ebCommand(self, f):
        e = f.trap(NotImplementedError, filetransfer.SFTPError, OSError, IOError)
        if e == NotImplementedError:
            self.transport.write(self.cmd_HELP(''))
        elif e == filetransfer.SFTPError:
            self.transport.write("remote error %i: %s\n" % 
                    (f.value.code, f.value.message))
        elif e in (OSError, IOError):
            self.transport.write("local error %i: %s\n" %
                    (f.value.errno, f.value.strerror))
            self._newLine()

    def cmd_CD(self, path):
        if not path.endswith('/'):
            path += '/'
        newPath = path and os.path.join(self.currentDirectory, path) or ''
        d = self.client.openDirectory(newPath)
        d.addCallback(self._cbCd, newPath)
        d.addErrback(self._ebCommand)
        return d

    def _cbCd(self, directory, newPath):
        directory.close()
        d = self.client.realPath(newPath)
        d.addCallback(self._cbCurDir)
        return d

    def _cbCurDir(self, path):
        self.currentDirectory = path

    def cmd_CHGRP(self, rest):
        grp, path = rest.split(' ', 1)
        grp = int(grp)
        d = self.client.getAttrs(path)
        d.addCallback(self._cbSetUsrGrp, path, grp=grp)
        return d
    
    def cmd_CHMOD(self, rest):
        mod, path = rest.split(' ', 1)
        mod = int(mod, 8)
        d = self.client.setAttrs(path, {'permissions':mod})
        d.addCallback(_ignore)
        return d
    
    def cmd_CHOWN(self, rest):
        usr, path = rest.split(' ', 1)
        usr = int(usr)
        d = self.client.getAttrs(path)
        d.addCallback(self._cbSetUsrGrp, path, usr=usr)
        return d
    
    def _cbSetUsrGrp(self, attrs, path, usr=None, grp=None):
        new = {}
        new['uid'] = (usr is not None) and usr or attrs['uid']
        new['gid'] = (grp is not None) and grp or attrs['gid']
        d = self.client.setAttrs(path, new)
        d.addCallback(_ignore)
        return d

    def cmd_GET(self, rest):
        numRequests = self.client.transport.conn.options['requests']
        if ' ' in rest:
            remote, local = rest.split()
        else:
            remote = local = rest
        lf = file(local, 'w')
        path = os.path.join(self.currentDirectory, remote)
        d = self.client.openFile(path, filetransfer.FXF_READ, {})
        d.addCallback(self._cbGetOpenFile, lf)
        d.addErrback(self._ebCloseLf, lf)
        return d

    def _ebCloseLf(self, f, lf):
        lf.close()
        return f

    def _cbGetOpenFile(self, rf, lf):
        bufferSize = self.client.transport.conn.options['buffersize']
        d = self._cbGetRead('', rf, lf, 0, bufferSize)
        d.addErrback(self._ebGetEOF, rf, lf)
        return d

    def _cbGetRead(self, data, rf, lf, start, bufSize):
        lf.seek(start)
        lf.write(data)
        d = rf.readChunk(start+len(data), bufSize)
        d.addCallback(self._cbGetRead, rf, lf, start+len(data), bufSize)
        return d

    def _ebGetEOF(self, f, rf, lf):
        f.trap(EOFError)
        rf.close()
        lf.close()
        return "transferred %s to %s" % ('remote', 'local')

    def cmd_PUT(self, rest):
        numRequests = self.client.transport.conn.options['requests']
        if ' ' in rest:
            local, remote= rest.split()
        else:
            remote = local = rest
        lf = file(local, 'r')
        path = os.path.join(self.currentDirectory, remote)
        d = self.client.openFile(path, filetransfer.FXF_WRITE|filetransfer.FXF_CREAT, {})
        d.addCallback(self._cbPutOpenFile, lf)
        d.addErrback(self._ebCloseLf, lf)
        return d

    def _cbPutOpenFile(self, rf, lf):
        bufferSize = self.client.transport.conn.options['buffersize']
        return self._cbPutWrite(None, rf, lf, 0, bufferSize)

    def _cbPutWrite(self, ignored, rf, lf, start, bufferSize):
        data = lf.read(bufferSize)
        if data:
            d = rf.writeChunk(start, data)
            d.addCallback(self._cbPutWrite, rf, lf, start+len(data), 
                            bufferSize)
            return d
        else:
            lf.close()
            rf.close()
            return 'transferred %s to %s' % ('local', 'remote')

    def cmd_LCD(self, path):
        os.chdir(path)

    def cmd_LN(self, rest):
        linkpath, targetpath = rest.split(' ')
        return self.client.makeLink(linkpath, targetpath).addCallback(_ignore)

    def cmd_LS(self, rest):
        # possible lines:
        # ls                    current directory
        # ls name_of_file       that file
        # ls name_of_directory  that directory
        # ls some_glob_string   current directory, globbed for that string
        rest += ' '
        if rest.startswith('-l '):
            verbose = 1
            rest = rest[3:]
        else:
            verbose = 0 
        rest = rest[:-1]
        fullPath = os.path.join(self.currentDirectory, rest)
        head, tail = os.path.split(fullPath)
        if '*' in tail or '?' in tail:
            glob = 1
        else:
            glob = 0
        if tail and not glob: # could be file or directory
           # try directory first
           d = self.client.openDirectory(fullPath)
           d.addCallback(self._cbOpenList, tail, verbose)
           d.addErrback(self._ebNotADirectory, head, tail, verbose)
        else:
            d = self.client.openDirectory(head)
            d.addCallback(self._cbOpenList, tail, verbose)
        return d

    def _cbOpenList(self, directory, glob, verbose):
        files = []
        d = directory.read()
        d.addBoth(self._cbReadFile, files, directory, self._cbDisplayFiles, glob, verbose)
        return d

    def _ebNotADirectory(self, reason, path, glob, verbose):
        d = self.client.openDirectory(path)
        d.addCallback(self._cbOpenList, glob, verbose)
        return d

    def _cbReadFile(self, files, l, directory, callback, *args):
        if not isinstance(files, failure.Failure):
            l.extend(files)
            d = directory.read()
            d.addBoth(self._cbReadFile, l, directory, callback, *args)
            return d
        else:
            reason = files
            reason.trap(EOFError)
            directory.close()
            return callback(l, *args)

    def _cbDisplayFiles(self, files, glob, verbose):
        if glob:
            files = [f for f in files if fnmatch.fnmatch(f[0], glob)]
        files.sort()
        if verbose:
            lines = [f[1] for f in files]
        else:
            lines = [f[0] for f in files]
        if not lines:
            return None
        else:
            return '\n'.join(lines)

    def cmd_MKDIR(self, path):
        path = os.path.join(self.currentDirectory, path)
        return self.client.makeDirectory(path, {}).addCallback(_ignore)

    def cmd_RMDIR(self, path):
        path = os.path.join(self.currentDirectory, path)
        return self.client.removeDirectory(path).addCallback(_ignore)

    def cmd_LMKDIR(self, path):
        os.system("mkdir %s" % path)

    def cmd_RM(self, path):
        path = os.path.join(self.currentDirectory, path)
        return self.client.removeFile(path).addCallback(_ignore)

    def cmd_LLS(self, rest):
        os.system("ls %s" % rest)

    def cmd_RENAME(self, rest):
        oldpath, newpath = rest.split(' ')
        return self.client.renameFile(oldpath, newpath).addCallback(_ignore)

    def cmd_EXIT(self, ignored):
        self.client.transport.loseConnection()

    cmd_QUIT = cmd_EXIT

    def cmd_VERSION(self, ignored):
        return "SFTP version %i" % self.client.version
    
    def cmd_HELP(self, ignored):
        return """Available commands:
cd path                         Change remote directory to 'path'.
chgrp gid path                  Change gid of 'path' to 'gid'.
chmod mode path                 Change mode of 'path' to 'mode'.
chown uid path                  Change uid of 'path' to 'uid'.
exit                            Disconnect from the server.
get remote-path [local-path]    Get remote file.
help                            Get a list of available commands.
lcd path                        Change local directory to 'path'.
lls [ls-options] [path]         Display local directory listing.
lmkdir path                     Create local directory.
ln linkpath targetpath          Symlink remote file.
lpwd                            Print the local working directory.
ls [-l] [path]                  Display remote directory listing.
mkdir path                      Create remote directory.
put local-path [remote-path]    Put local file.
pwd                             Print the remote working directory.
quit                            Disconnect from the server.
rename oldpath newpath          Rename remote file.
rmdir path                      Remove remote directory.
rm path                         Remove remote file.
version                         Print the SFTP version.
?                               Synonym for 'help'.
"""

    def cmd_PWD(self, ignored):
        return self.currentDirectory

    def cmd_LPWD(self, ignored):
        return os.getcwd()

StdioClient.__dict__['cmd_?'] = StdioClient.cmd_HELP

class SSHConnection(connection.SSHConnection):
    def serviceStarted(self):
        self.openChannel(SSHSession())

class FromFile(abstract.FileDescriptor):
    def __init__(self, fileno, protocol):
        abstract.FileDescriptor.__init__(self)
        self.fileno = lambda: fileno
        fdesc.setNonBlocking(self.fileno())
        self.protocol = protocol
        self.startReading()
        self.writer = stdio.StandardIOWriter()
        self.write = self.writer.write
        self.closeStdin = self.writer.loseConnection
        self.connectionLost = self.protocol.connectionLost
        self.protocol.makeConnection(self)

    def doRead(self):
        fdesc.readFromFD(self.fileno(), self.protocol.dataReceived)

class SSHSession(channel.SSHChannel):

    name = 'session'

    def channelOpen(self, foo):
        log.msg('session %s open' % self.id)
        if self.conn.options['subsystem'].startswith('/'):
            request = 'exec'
        else:
            request = 'subsystem'
        d = self.conn.sendRequest(self, request, \
            common.NS(self.conn.options['subsystem']), wantReply=1)
        d.addCallback(self._cbSubsystem)
        d.addErrback(_ebExit)

    def _cbSubsystem(self, result):
        self.client = filetransfer.FileTransferClient()
        self.client.makeConnection(self)
        self.dataReceived = self.client.dataReceived
        if self.conn.options['batchfile']:
            f = self.conn.options['batchfile']
            if f == '-':
                fileno = 0
            else:
                fileno = open(f, 'r').fileno()
            self.stdio = FromFile(fileno, StdioClient(self.client))
        else:
            self.stdio = stdio.StandardIO(StdioClient(self.client))

    def extReceived(self, t, data):
        if t==connection.EXTENDED_DATA_STDERR:
            log.msg('got %s stderr data' % len(data))
            sys.stderr.write(data)
            sys.stderr.flush()

    def eofReceived(self):
        log.msg('got eof')
        self.stdio.closeStdin()
    
    def closeReceived(self):
        log.msg('remote side closed %s' % self)
        self.conn.sendClose(self)

    def closed(self):
        try:
            reactor.stop()
        except:
            pass

    def stopWriting(self):
        self.stdio.stopReading()

    def startWriting(self):
        self.stdio.startReading()

if __name__ == '__main__':
    run()

