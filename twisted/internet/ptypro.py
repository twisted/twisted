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

"""UNIX PTY Process management.

API Stability: unstable

Future Plans: merge into IReactorProcess API

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import os, sys, traceback, errno, pty

from twisted.persisted import styles
from twisted.python import log

# Sibling Imports
import abstract, main, fdesc, process
from main import CONNECTION_LOST


class Process(abstract.FileDescriptor, styles.Ephemeral):
    """An operating-system Process that uses PTY support."""

    def __init__(self, command, args, environment, path, proto,
                 uid=None, gid=None):
        """Spawn an operating-system process.

        This is where the hard work of disconnecting all currently open
        files / forking / executing the new process happens.  (This is
        executed automatically when a Process is instantiated.)

        This will also run the subprocess as a given user ID and group ID, if
        specified.  (Implementation Note: this doesn't support all the arcane
        nuances of setXXuid on UNIX: it will assume that either your effective
        or real UID is 0.)
        """
        abstract.FileDescriptor.__init__(self)
        pid, fd = pty.fork()
        if pid == 0: # pid is 0 in the child process
            sys.settrace(None)
            try:
                if path:
                    os.chdir(path)
                os.execvpe(command, args, environment)
            except:
                traceback.print_exc(file=log.logfile)
                os._exit(1)
        fdesc.setNonBlocking(fd)
        self.fd=fd
        self.startReading()
        self.connected = 1
        self.proto = proto
        try:
            self.proto.makeConnection(self)
        except:
            log.deferr()

    def doRead(self):
        """Called when my standard output stream is ready for reading.
        """
        try:
            return fdesc.readFromFD(self.fd, self.proto.dataReceived)
        except OSError:
            return CONNECTION_LOST

    def fileno(self):
        """This returns the file number of standard output on this process.
        """
        return self.fd

    def maybeCallProcessEnded(self):
        try:
            self.proto.processEnded()
        except:
            log.deferr()
            process.reapProcess()

    def connectionLost(self, reason):
        """I call this to clean up when one or all of my connections has died.
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        os.close(self.fd)
        try:
            self.proto.connectionLost()
        except:
            log.deferr()
        self.maybeCallProcessEnded()

    def writeSomeData(self, data):
        """Write some data to the open process.
        """
        try:
            rv = os.write(self.fd, self.unsent)
            if rv == len(self.unsent):
                self.startReading()
            return rv
        except IOError, io:
            if io.args[0] == errno.EAGAIN:
                return 0
            return CONNECTION_LOST
        except OSError, ose:
            if ose.errno == errno.EPIPE:
                return CONNECTION_LOST
            raise

    def write(self, data):
        self.stopReading()
        abstract.FileDescriptor.write(self, data)
