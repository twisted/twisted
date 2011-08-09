# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An implementation of
U{Web Resource Gateway Interface<http://www.python.org/dev/peps/pep-0333/>}.
"""

__metaclass__ = type

from sys import exc_info

from zope.interface import implements

from twisted.python.log import msg, err
from twisted.python.failure import Failure
from twisted.web.resource import IResource
from twisted.web.server import NOT_DONE_YET
from twisted.web.http import INTERNAL_SERVER_ERROR


class _ErrorStream:
    """
    File-like object instances of which are used as the value for the
    C{'wsgi.errors'} key in the C{environ} dictionary passed to the application
    object.

    This simply passes writes on to L{logging<twisted.python.log>} system as
    error events from the C{'wsgi'} system.  In the future, it may be desirable
    to expose more information in the events it logs, such as the application
    object which generated the message.
    """
    def write(self, bytes):
        """
        Generate an event for the logging system with the given bytes as the
        message.

        This is called in a WSGI application thread, not the I/O thread.
        """
        msg(bytes, system='wsgi', isError=True)


    def writelines(self, iovec):
        """
        Join the given lines and pass them to C{write} to be handled in the
        usual way.

        This is called in a WSGI application thread, not the I/O thread.

        @param iovec: A C{list} of C{'\\n'}-terminated C{str} which will be
            logged.
        """
        self.write(''.join(iovec))


    def flush(self):
        """
        Nothing is buffered, so flushing does nothing.  This method is required
        to exist by PEP 333, though.

        This is called in a WSGI application thread, not the I/O thread.
        """



class _InputStream:
    """
    File-like object instances of which are used as the value for the
    C{'wsgi.input'} key in the C{environ} dictionary passed to the application
    object.

    This only exists to make the handling of C{readline(-1)} consistent across
    different possible underlying file-like object implementations.  The other
    supported methods pass through directly to the wrapped object.
    """
    def __init__(self, input):
        """
        Initialize the instance.

        This is called in the I/O thread, not a WSGI application thread.
        """
        self._wrapped = input


    def read(self, size=None):
        """
        Pass through to the underlying C{read}.

        This is called in a WSGI application thread, not the I/O thread.
        """
        # Avoid passing None because cStringIO and file don't like it.
        if size is None:
            return self._wrapped.read()
        return self._wrapped.read(size)


    def readline(self, size=None):
        """
        Pass through to the underlying C{readline}, with a size of C{-1} replaced
        with a size of C{None}.

        This is called in a WSGI application thread, not the I/O thread.
        """
        # Check for -1 because StringIO doesn't handle it correctly.  Check for
        # None because files and tempfiles don't accept that.
        if size == -1 or size is None:
            return self._wrapped.readline()
        return self._wrapped.readline(size)


    def readlines(self, size=None):
        """
        Pass through to the underlying C{readlines}.

        This is called in a WSGI application thread, not the I/O thread.
        """
        # Avoid passing None because cStringIO and file don't like it.
        if size is None:
            return self._wrapped.readlines()
        return self._wrapped.readlines(size)


    def __iter__(self):
        """
        Pass through to the underlying C{__iter__}.

        This is called in a WSGI application thread, not the I/O thread.
        """
        return iter(self._wrapped)



class _WSGIResponse:
    """
    Helper for L{WSGIResource} which drives the WSGI application using a
    threadpool and hooks it up to the L{Request}.

    @ivar started: A C{bool} indicating whether or not the response status and
        headers have been written to the request yet.  This may only be read or
        written in the WSGI application thread.

    @ivar reactor: An L{IReactorThreads} provider which is used to call methods
        on the request in the I/O thread.

    @ivar threadpool: A L{ThreadPool} which is used to call the WSGI
        application object in a non-I/O thread.

    @ivar application: The WSGI application object.

    @ivar request: The L{Request} upon which the WSGI environment is based and
        to which the application's output will be sent.

    @ivar environ: The WSGI environment C{dict}.

    @ivar status: The HTTP response status C{str} supplied to the WSGI
        I{start_response} callable by the application.

    @ivar headers: A list of HTTP response headers supplied to the WSGI
        I{start_response} callable by the application.

    @ivar _requestFinished: A flag which indicates whether it is possible to
        generate more response data or not.  This is C{False} until
        L{Request.notifyFinish} tells us the request is done, then C{True}.
    """

    _requestFinished = False

    def __init__(self, reactor, threadpool, application, request):
        self.started = False
        self.reactor = reactor
        self.threadpool = threadpool
        self.application = application
        self.request = request
        self.request.notifyFinish().addBoth(self._finished)

        if request.prepath:
            scriptName = '/' + '/'.join(request.prepath)
        else:
            scriptName = ''

        if request.postpath:
            pathInfo = '/' + '/'.join(request.postpath)
        else:
            pathInfo = ''

        parts = request.uri.split('?', 1)
        if len(parts) == 1:
            queryString = ''
        else:
            queryString = parts[1]

        self.environ = {
            'REQUEST_METHOD': request.method,
            'REMOTE_ADDR': request.getClientIP(),
            'SCRIPT_NAME': scriptName,
            'PATH_INFO': pathInfo,
            'QUERY_STRING': queryString,
            'CONTENT_TYPE': request.getHeader('content-type') or '',
            'CONTENT_LENGTH': request.getHeader('content-length') or '',
            'SERVER_NAME': request.getRequestHostname(),
            'SERVER_PORT': str(request.getHost().port),
            'SERVER_PROTOCOL': request.clientproto}


        # The application object is entirely in control of response headers;
        # disable the default Content-Type value normally provided by
        # twisted.web.server.Request.
        self.request.defaultContentType = None

        for name, values in request.requestHeaders.getAllRawHeaders():
            name = 'HTTP_' + name.upper().replace('-', '_')
            # It might be preferable for http.HTTPChannel to clear out
            # newlines.
            self.environ[name] = ','.join([
                    v.replace('\n', ' ') for v in values])

        self.environ.update({
                'wsgi.version': (1, 0),
                'wsgi.url_scheme': request.isSecure() and 'https' or 'http',
                'wsgi.run_once': False,
                'wsgi.multithread': True,
                'wsgi.multiprocess': False,
                'wsgi.errors': _ErrorStream(),
                # Attend: request.content was owned by the I/O thread up until
                # this point.  By wrapping it and putting the result into the
                # environment dictionary, it is effectively being given to
                # another thread.  This means that whatever it is, it has to be
                # safe to access it from two different threads.  The access
                # *should* all be serialized (first the I/O thread writes to
                # it, then the WSGI thread reads from it, then the I/O thread
                # closes it).  However, since the request is made available to
                # arbitrary application code during resource traversal, it's
                # possible that some other code might decide to use it in the
                # I/O thread concurrently with its use in the WSGI thread.
                # More likely than not, this will break.  This seems like an
                # unlikely possibility to me, but if it is to be allowed,
                # something here needs to change. -exarkun
                'wsgi.input': _InputStream(request.content)})


    def _finished(self, ignored):
        """
        Record the end of the response generation for the request being
        serviced.
        """
        self._requestFinished = True


    def startResponse(self, status, headers, excInfo=None):
        """
        The WSGI I{start_response} callable.  The given values are saved until
        they are needed to generate the response.

        This will be called in a non-I/O thread.
        """
        if self.started and excInfo is not None:
            raise excInfo[0], excInfo[1], excInfo[2]
        self.status = status
        self.headers = headers
        return self.write


    def write(self, bytes):
        """
        The WSGI I{write} callable returned by the I{start_response} callable.
        The given bytes will be written to the response body, possibly flushing
        the status and headers first.

        This will be called in a non-I/O thread.
        """
        def wsgiWrite(started):
            if not started:
                self._sendResponseHeaders()
            self.request.write(bytes)
        self.reactor.callFromThread(wsgiWrite, self.started)
        self.started = True


    def _sendResponseHeaders(self):
        """
        Set the response code and response headers on the request object, but
        do not flush them.  The caller is responsible for doing a write in
        order for anything to actually be written out in response to the
        request.

        This must be called in the I/O thread.
        """
        code, message = self.status.split(None, 1)
        code = int(code)
        self.request.setResponseCode(code, message)

        for name, value in self.headers:
            # Don't allow the application to control these required headers.
            if name.lower() not in ('server', 'date'):
                self.request.responseHeaders.addRawHeader(name, value)


    def start(self):
        """
        Start the WSGI application in the threadpool.

        This must be called in the I/O thread.
        """
        self.threadpool.callInThread(self.run)


    def run(self):
        """
        Call the WSGI application object, iterate it, and handle its output.

        This must be called in a non-I/O thread (ie, a WSGI application
        thread).
        """
        try:
            appIterator = self.application(self.environ, self.startResponse)
            for elem in appIterator:
                if elem:
                    self.write(elem)
                if self._requestFinished:
                    break
            close = getattr(appIterator, 'close', None)
            if close is not None:
                close()
        except:
            def wsgiError(started, type, value, traceback):
                err(Failure(value, type, traceback), "WSGI application error")
                if started:
                    self.request.transport.loseConnection()
                else:
                    self.request.setResponseCode(INTERNAL_SERVER_ERROR)
                    self.request.finish()
            self.reactor.callFromThread(wsgiError, self.started, *exc_info())
        else:
            def wsgiFinish(started):
                if not self._requestFinished:
                    if not started:
                        self._sendResponseHeaders()
                    self.request.finish()
            self.reactor.callFromThread(wsgiFinish, self.started)
        self.started = True



class WSGIResource:
    """
    An L{IResource} implementation which delegates responsibility for all
    resources hierarchically inferior to it to a WSGI application.

    @ivar _reactor: An L{IReactorThreads} provider which will be passed on to
        L{_WSGIResponse} to schedule calls in the I/O thread.

    @ivar _threadpool: A L{ThreadPool} which will be passed on to
        L{_WSGIResponse} to run the WSGI application object.

    @ivar _application: The WSGI application object.
    """
    implements(IResource)

    # Further resource segments are left up to the WSGI application object to
    # handle.
    isLeaf = True

    def __init__(self, reactor, threadpool, application):
        self._reactor = reactor
        self._threadpool = threadpool
        self._application = application


    def render(self, request):
        """
        Turn the request into the appropriate C{environ} C{dict} suitable to be
        passed to the WSGI application object and then pass it on.

        The WSGI application object is given almost complete control of the
        rendering process.  C{NOT_DONE_YET} will always be returned in order
        and response completion will be dictated by the application object, as
        will the status, headers, and the response body.
        """
        response = _WSGIResponse(
            self._reactor, self._threadpool, self._application, request)
        response.start()
        return NOT_DONE_YET


    def getChildWithDefault(self, name, request):
        """
        Reject attempts to retrieve a child resource.  All path segments beyond
        the one which refers to this resource are handled by the WSGI
        application object.
        """
        raise RuntimeError("Cannot get IResource children from WSGIResource")


    def putChild(self, path, child):
        """
        Reject attempts to add a child resource to this resource.  The WSGI
        application object handles all path segments beneath this resource, so
        L{IResource} children can never be found.
        """
        raise RuntimeError("Cannot put IResource children under WSGIResource")


__all__ = ['WSGIResource']
