# -*- test-case-name: twisted.web2.test.test_wsgi -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An implementation of PEP 333: Python Web Server Gateway Interface (WSGI).
"""

import os, threading
from zope.interface import implements

from twisted.internet import defer, threads
from twisted.internet import reactor
from twisted.python import log, failure
from twisted.web2 import http
from twisted.web2 import iweb
from twisted.web2 import server
from twisted.web2 import stream
from twisted.web2.twcgi import createCGIEnvironment


class AlreadyStartedResponse(Exception):
    pass


# This isn't a subclass of resource.Resource, because it shouldn't do
# any method-specific actions at all. All that stuff is totally up to
# the contained wsgi application
class WSGIResource(object):
    """
    A web2 Resource which wraps the given WSGI application callable.

    The WSGI application will be called in a separate thread (using
    the reactor threadpool) whenever a request for this resource or
    any lower part of the url hierarchy is received.
    """
    implements(iweb.IResource)

    def __init__(self, application):
        self.application = application

    def renderHTTP(self, req):
        # Do stuff with WSGIHandler.
        handler = WSGIHandler(self.application, req)
        # Get deferred
        d = handler.responseDeferred
        # Run it in a thread
        reactor.callInThread(handler.run)
        return d

    def locateChild(self, request, segments):
        return self, server.StopTraversal


class InputStream(object):
    """
    This class implements the 'wsgi.input' object. The methods are
    expected to have the same behavior as the same-named methods for
    python's builtin file object.
    """

    def __init__(self, newstream):
        # Called in IO thread
        self.stream = stream.BufferedStream(newstream)

    def read(self, size=None):
        """
        Read at most size bytes from the input, or less if EOF is
        encountered. If size is ommitted or negative, read until EOF.
        """
        # Called in application thread
        if size < 0:
            size = None
        return threads.blockingCallFromThread(
            reactor, self.stream.readExactly, size)

    def readline(self, size=None):
        """
        Read a line, delimited by a newline. If the stream reaches EOF
        or size bytes have been read before reaching a newline (if
        size is given), the partial line is returned.

        COMPATIBILITY NOTE: the size argument is excluded from the
        WSGI specification, but is provided here anyhow, because
        useful libraries such as python stdlib's cgi.py assume their
        input file-like-object supports readline with a size
        argument. If you use it, be aware your application may not be
        portable to other conformant WSGI servers.
        """
        # Called in application thread
        if size < 0:
            # E.g. -1, which is the default readline size for *some*
            # other file-like-objects...
            size = None

        return threads.blockingCallFromThread(
            reactor, self.stream.readline, '\n', size=size)

    def readlines(self, hint=None):
        """
        Read until EOF, collecting all lines in a list, and returns
        that list. The hint argument is ignored (as is allowed in the
        API specification)
        """
        # Called in application thread
        data = self.read()
        lines = data.split('\n')
        last = lines.pop()
        lines = [s+'\n' for s in lines]
        if last != '':
            lines.append(last)
        return lines

    def __iter__(self):
        """
        Returns an iterator, each iteration of which returns the
        result of readline(), and stops when readline() returns an
        empty string.
        """
        while 1:
            line = self.readline()
            if not line:
                return
            yield line


class ErrorStream(object):
    """
    This class implements the 'wsgi.error' object.
    """
    def flush(self):
        # Called in application thread
        return

    def write(self, s):
        # Called in application thread
        log.msg("WSGI app error: "+s, isError=True)

    def writelines(self, seq):
        # Called in application thread
        s = ''.join(seq)
        log.msg("WSGI app error: "+s, isError=True)

class WSGIHandler(object):
    headersSent = False
    stopped = False
    stream = None

    def __init__(self, application, request):
        # Called in IO thread
        self.setupEnvironment(request)
        self.application = application
        self.request = request
        self.response = None
        self.responseDeferred = defer.Deferred()

    def setupEnvironment(self, request):
        # Called in IO thread
        env = createCGIEnvironment(request)
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = env['REQUEST_SCHEME']
        env['wsgi.input']        = InputStream(request.stream)
        env['wsgi.errors']       = ErrorStream()
        env['wsgi.multithread']  = True
        env['wsgi.multiprocess'] = False
        env['wsgi.run_once']     = False
        env['wsgi.file_wrapper'] = FileWrapper
        self.environment = env

    def startWSGIResponse(self, status, response_headers, exc_info=None):
        # Called in application thread
        if exc_info is not None:
            try:
                if self.headersSent:
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                exc_info = None
        elif self.response is not None:
            raise AlreadyStartedResponse, 'startWSGIResponse(%r)' % status
        status = int(status.split(' ')[0])
        self.response = http.Response(status)
        for key, value in response_headers:
            self.response.headers.addRawHeader(key, value)
        return self.write


    def run(self):
        # Called in application thread
        try:
            result = self.application(self.environment, self.startWSGIResponse)
            self.handleResult(result)
        except:
            if not self.headersSent:
                reactor.callFromThread(self.__error, failure.Failure())
            else:
                reactor.callFromThread(self.stream.finish, failure.Failure())

    def __callback(self):
        # Called in IO thread
        self.responseDeferred.callback(self.response)
        self.responseDeferred = None

    def __error(self, f):
        # Called in IO thread
        self.responseDeferred.errback(f)
        self.responseDeferred = None

    def write(self, output):
        # Called in application thread
        if self.response is None:
            raise RuntimeError(
                "Application didn't call startResponse before writing data!")
        if not self.headersSent:
            self.stream=self.response.stream=stream.ProducerStream()
            self.headersSent = True

            # threadsafe event object to communicate paused state.
            self.unpaused = threading.Event()

            # After this, we cannot touch self.response from this
            # thread any more
            def _start():
                # Called in IO thread
                self.stream.registerProducer(self, True)
                self.__callback()
                # Notify application thread to start writing
                self.unpaused.set()
            reactor.callFromThread(_start)
        # Wait for unpaused to be true
        self.unpaused.wait()
        reactor.callFromThread(self.stream.write, output)

    def writeAll(self, result):
        # Called in application thread
        if not self.headersSent:
            if self.response is None:
                raise RuntimeError(
                    "Application didn't call startResponse before writing data!")
            l = 0
            for item in result:
                l += len(item)
            self.response.stream=stream.ProducerStream(length=l)
            self.response.stream.buffer = list(result)
            self.response.stream.finish()
            reactor.callFromThread(self.__callback)
        else:
            # Has already been started, cannot replace the stream
            def _write():
                # Called in IO thread
                for s in result:
                    self.stream.write(s)
                self.stream.finish()
            reactor.callFromThread(_write)


    def handleResult(self, result):
        # Called in application thread
        try:
            if (isinstance(result, FileWrapper) and
                   hasattr(result.filelike, 'fileno') and
                   not self.headersSent):
                if self.response is None:
                    raise RuntimeError(
                        "Application didn't call startResponse before writing data!")
                self.headersSent = True
                # Make FileStream and output it. We make a new file
                # object from the fd, just in case the original one
                # isn't an actual file object.
                self.response.stream = stream.FileStream(
                    os.fdopen(os.dup(result.filelike.fileno())))
                reactor.callFromThread(self.__callback)
                return

            if type(result) in (list,tuple):
                # If it's a list or tuple (exactly, not subtype!),
                # then send the entire thing down to Twisted at once,
                # and free up this thread to do other work.
                self.writeAll(result)
                return

            # Otherwise, this thread has to keep running to provide the
            # data.
            for data in result:
                if self.stopped:
                    return
                self.write(data)

            if not self.headersSent:
                if self.response is None:
                    raise RuntimeError(
                        "Application didn't call startResponse, and didn't send any data!")

                self.headersSent = True
                reactor.callFromThread(self.__callback)
            else:
                reactor.callFromThread(self.stream.finish)

        finally:
            if hasattr(result,'close'):
                result.close()

    def pauseProducing(self):
        # Called in IO thread
        self.unpaused.set()

    def resumeProducing(self):
        # Called in IO thread
        self.unpaused.clear()

    def stopProducing(self):
        self.stopped = True

class FileWrapper(object):
    """
    Wrapper to convert file-like objects to iterables, to implement
    the optional 'wsgi.file_wrapper' object.
    """

    def __init__(self, filelike, blksize=8192):
        self.filelike = filelike
        self.blksize = blksize
        if hasattr(filelike,'close'):
            self.close = filelike.close

    def __iter__(self):
        return self

    def next(self):
        data = self.filelike.read(self.blksize)
        if data:
            return data
        raise StopIteration

__all__ = ['WSGIResource']
