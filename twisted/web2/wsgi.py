"""
A non-blocking container resource for WSGI web applications.
"""

import os, threading
import Queue
from zope.interface import implements

from twisted.internet import defer
from twisted.python import log, failure
from twisted.web2 import http
from twisted.web2 import iweb
from twisted.web2 import responsecode
from twisted.web2 import server
from twisted.web2 import stream
from twisted.web2.twcgi import createCGIEnvironment


class AlreadyStartedResponse(Exception):
    pass


# This isn't a subclass of resource.Resource, because it shouldn't do
# any method-specific actions at all. All that stuff is totally up to
# the contained wsgi application
class WSGIResource(object):
    implements(iweb.IResource)
    
    def __init__(self, application):
        self.application = application

    def renderHTTP(self, ctx):
        from twisted.internet import reactor
        # Do stuff with WSGIHandler.
        handler = WSGIHandler(self.application, ctx)
        # Get deferred
        d = handler.responseDeferred
        # Run it in a thread
        reactor.callInThread(handler.run)
        return d
    
    def locateChild(self, request, segments):
        return self, server.StopTraversal
            
def callInReactor(__f, *__a, **__kw):
    from twisted.internet import reactor
    queue = Queue.Queue()
    reactor.callFromThread(__callFromThread, queue, __f, __a, __kw)
    result = queue.get()
    if isinstance(result, failure.Failure):
        result.raiseException()
    return result

def __callFromThread(queue, f, a, kw):
    result = defer.maybeDeferred(f, *a, **kw)
    result.addBoth(queue.put)

class InputStream(object):
    def __init__(self, newstream):
        self.stream = stream.BufferedStream(newstream)
        
    def read(self, size=None):
        return callInReactor(self.stream.readExactly, size)

    def readline(self):
        return callInReactor(self.stream.readline, '\n')+'\n'
    
    def readlines(self, hint):
        data = self.read()
        return [s+'\n' for s in data.split('\n')]

class ErrorStream(object):
    def flush(self):
        return

    def write(self, s):
        from twisted.internet import reactor
        log.msg("WSGI app error: "+s, isError=True)

    def writelines(self, seq):
        from twisted.internet import reactor
        s = ''.join(seq)
        log.msg("WSGI app error: "+s, isError=True)

class WSGIHandler(object):
    headersSent = False
    
    def __init__(self, application, ctx):
        # Called in IO thread
        request = iweb.IRequest(ctx)
        self.environment = createCGIEnvironment(ctx, request)
        self.application = application
        self.request = request
        self.response = None
        self.responseDeferred = defer.Deferred()
        # threadsafe event object to communicate paused state.
        self.unpaused = threading.Event()

    def setupEnvironment(self):
        # Called in application thread
        env = self.environment
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = env['REQUEST_SCHEME']
        env['wsgi.input']        = InputStream(self.request.stream)
        env['wsgi.errors']       = ErrorStream()
        env['wsgi.multithread']  = True
        env['wsgi.multiprocess'] = True
        env['wsgi.run_once']     = False
        env['wsgi.file_wrapper'] = FileWrapper

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
            self.setupEnvironment()
            result = self.application(self.environment, self.startWSGIResponse)
            self.handleResult(result)
        except:
            log.err()


    def __callback(self):
        # Called in IO thread
        self.responseDeferred.callback(self.response)
        self.responseDeferred = None
        
    def write(self, output):
        # Called in application thread
        from twisted.internet import reactor
        if not self.headersSent:
            self.response.stream=stream.ProducerStream()
            self.headersSent = True
            
            # After this, we cannot touch self.response from this
            # thread any more
            def _start():
                # Called in IO thread
                self.response.stream.registerProducer(self, True)
                self.__callback()
                # Notify application thread to start writing
                self.unpaused.set()
            reactor.callFromThread(_start)
        # Wait for unpaused to be true
        self.unpaused.wait()
        reactor.callFromThread(self.response.stream.write, output)


    def handleResult(self, result):
        # Called in application thread
        try:
            from twisted.internet import reactor
            if (isinstance(result, FileWrapper) and 
                   hasattr(result.filelike, 'fileno') and
                   not self.headersSent):
                self.headersSent = True
                # Make FileStream and output it. We make a new file
                # object from the fd, just in case the original one
                # isn't an actual file object.
                self.response.stream = stream.FileStream(
                    os.fdopen(os.dup(result.filelike.fileno())))
                reactor.callFromThread(self.__callback)
                return
            
            for data in result:
                self.write(data)
                
            if not self.headersSent:
                self.headersSent = True
                reactor.callFromThread(self.__callback)
            else:
                reactor.callFromThread(self.response.stream.finish)
                
        finally:
            if hasattr(result,'close'):
                result.close()

    def pauseProducing(self):
        # Called in IO thread
        self.unpaused.set()

    def resumeProducing(self):
        # Called in IO thread
        self.unpaused.clear()
        

class FileWrapper:
    """Wrapper to convert file-like objects to iterables"""

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
