from twisted.internet import reactor, defer
from twisted.python.failure import Failure

import greenlet

import socket
import errno
import os
from sets import Set

class GreenSocket(socket.socket):
    wraps = Set()
    def logPrefix(self):
        return "monkey"

    def connect(self, addr):
        supr = super(GreenSocket, self)
        cur = greenlet.getcurrent()
        if cur not in self.wraps or self.gettimeout == 0.0:
            return supr.connect(addr)
        else:
            self.glet = cur
            timeout = self.gettimeout()
            self.setblocking(False)
            try:
                    try:
                        supr.connect(addr)
                    except socket.error, se:
                        if se.args[0] != errno.EINPROGRESS:
                            raise
                    reactor.addWriter(self)
                    cur.parent.switch()
                    err = self.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if err:
                        raise socket.error(err, os.strerror(err))
            finally:
                del self.glet
                reactor.removeWriter(self)
                self.settimeout(timeout)

    def recv(self, bufsize, flags = 0):
        supr = super(GreenSocket, self)
        cur = greenlet.getcurrent()
        if cur not in self.wraps or self.gettimeout == 0.0:
            return supr.recv(bufsize, flags)
        else:
            self.glet = cur
            timeout = self.gettimeout()
            self.setblocking(False)
            reactor.addReader(self)
            try:
                while 1:
                    cur.parent.switch()
                    try:
                        return(supr.recv(bufsize))
                    except socket.error, se:
                        if se.args[0] != errno.EWOULDBLOCK:
                            raise
            finally:
                del self.glet
                reactor.removeReader(self)
                self.settimeout(timeout)

    def doRead(self):
        self.glet.switch()

    def send(self, data, flags = 0):
        supr = super(GreenSocket, self)
        cur = greenlet.getcurrent()
        if cur not in self.wraps or self.gettimeout == 0.0:
            return supr.send(data, flags)
        else:
            self.glet = cur
            timeout = self.gettimeout()
            self.setblocking(False)
            reactor.addWriter(self)
            try:
                while 1:
                    cur.parent.switch()
                    try:
                        return(supr.send(data, flags))
                    except socket.error, se:
                        if se.args[0] != errno.EWOULDBLOCK:
                            raise
            finally:
                del self.glet
                reactor.removeWriter(self)
                self.settimeout(timeout)

    def doWrite(self):
        self.glet.switch()

def _wrapper(d, f, args, kw):
    try:
        d.callback(f(*args, **kw))
    except:
        d.errback()

def wrapCall(f, *args, **kw):
    d = defer.Deferred()
    gr = greenlet.greenlet(_wrapper)
    try:
        GreenSocket.wraps.add(gr)
        gr.switch(d, f, args, kw)
        return d
    finally:
        GreenSocket.wraps.remove(gr)

