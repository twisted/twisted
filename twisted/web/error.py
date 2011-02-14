# -*- test-case-name: twisted.web.test.test_error -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Exception definitions for L{twisted.web}.
"""

import operator, warnings

from twisted.web import http


class Error(Exception):
    """
    A basic HTTP error.

    @type status: C{str}
    @ivar status: Refers to an HTTP status code, for example L{http.NOT_FOUND}.

    @type message: C{str}
    @param message: A short error message, for example "NOT FOUND".

    @type response: C{str}
    @ivar response: A complete HTML document for an error page.
    """
    def __init__(self, code, message=None, response=None):
        """
        Initializes a basic exception.

        @type code: C{str}
        @param code: Refers to an HTTP status code, for example
            L{http.NOT_FOUND}. If no C{message} is given, C{code} is mapped to a
            descriptive string that is used instead.

        @type message: C{str}
        @param message: A short error message, for example "NOT FOUND".

        @type response: C{str}
        @param response: A complete HTML document for an error page.
        """
        if not message:
            try:
                message = http.responses.get(int(code))
            except ValueError:
                # If code wasn't a stringified int, can't map the
                # status code to a descriptive string so keep message
                # unchanged.
                pass

        Exception.__init__(self, code, message, response)
        self.status = code
        self.message = message
        self.response = response


    def __str__(self):
        return '%s %s' % (self[0], self[1])



class PageRedirect(Error):
    """
    A request resulted in an HTTP redirect.

    @type location: C{str}
    @ivar location: The location of the redirect which was not followed.
    """
    def __init__(self, code, message=None, response=None, location=None):
        """
        Initializes a page redirect exception.

        @type code: C{str}
        @param code: Refers to an HTTP status code, for example
            L{http.NOT_FOUND}. If no C{message} is given, C{code} is mapped to a
            descriptive string that is used instead.

        @type message: C{str}
        @param message: A short error message, for example "NOT FOUND".

        @type response: C{str}
        @param response: A complete HTML document for an error page.

        @type location: C{str}
        @param location: The location response-header field value. It is an
            absolute URI used to redirect the receiver to a location other than
            the Request-URI so the request can be completed.
        """
        if not message:
            try:
                message = http.responses.get(int(code))
            except ValueError:
                # If code wasn't a stringified int, can't map the
                # status code to a descriptive string so keep message
                # unchanged.
                pass

        if location and message:
            message = "%s to %s" % (message, location)

        Error.__init__(self, code, message, response)
        self.location = location



class InfiniteRedirection(Error):
    """
    HTTP redirection is occurring endlessly.

    @type location: C{str}
    @ivar location: The first URL in the series of redirections which was
        not followed.
    """
    def __init__(self, code, message=None, response=None, location=None):
        """
        Initializes an infinite redirection exception.

        @type code: C{str}
        @param code: Refers to an HTTP status code, for example
            L{http.NOT_FOUND}. If no C{message} is given, C{code} is mapped to a
            descriptive string that is used instead.

        @type message: C{str}
        @param message: A short error message, for example "NOT FOUND".

        @type response: C{str}
        @param response: A complete HTML document for an error page.

        @type location: C{str}
        @param location: The location response-header field value. It is an
            absolute URI used to redirect the receiver to a location other than
            the Request-URI so the request can be completed.
        """
        if not message:
            try:
                message = http.responses.get(int(code))
            except ValueError:
                # If code wasn't a stringified int, can't map the
                # status code to a descriptive string so keep message
                # unchanged.
                pass

        if location and message:
            message = "%s to %s" % (message, location)

        Error.__init__(self, code, message, response)
        self.location = location



class UnsupportedMethod(Exception):
    """
    Raised by a resource when faced with a strange request method.

    RFC 2616 (HTTP 1.1) gives us two choices when faced with this situtation:
    If the type of request is known to us, but not allowed for the requested
    resource, respond with NOT_ALLOWED.  Otherwise, if the request is something
    we don't know how to deal with in any case, respond with NOT_IMPLEMENTED.

    When this exception is raised by a Resource's render method, the server
    will make the appropriate response.

    This exception's first argument MUST be a sequence of the methods the
    resource *does* support.
    """

    allowedMethods = ()

    def __init__(self, allowedMethods, *args):
        Exception.__init__(self, allowedMethods, *args)
        self.allowedMethods = allowedMethods

        if not operator.isSequenceType(allowedMethods):
            why = "but my first argument is not a sequence."
            s = ("First argument must be a sequence of"
                 " supported methods, %s" % (why,))
            raise TypeError, s



class SchemeNotSupported(Exception):
    """
    The scheme of a URI was not one of the supported values.
    """



from twisted.web import resource as _resource

class ErrorPage(_resource.ErrorPage):
    """
    Deprecated alias for L{twisted.web.resource.ErrorPage}.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "twisted.web.error.ErrorPage is deprecated since Twisted 9.0.  "
            "See twisted.web.resource.ErrorPage.", DeprecationWarning,
            stacklevel=2)
        _resource.ErrorPage.__init__(self, *args, **kwargs)



class NoResource(_resource.NoResource):
    """
    Deprecated alias for L{twisted.web.resource.NoResource}.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "twisted.web.error.NoResource is deprecated since Twisted 9.0.  "
            "See twisted.web.resource.NoResource.", DeprecationWarning,
            stacklevel=2)
        _resource.NoResource.__init__(self, *args, **kwargs)



class ForbiddenResource(_resource.ForbiddenResource):
    """
    Deprecated alias for L{twisted.web.resource.ForbiddenResource}.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "twisted.web.error.ForbiddenResource is deprecated since Twisted "
            "9.0.  See twisted.web.resource.ForbiddenResource.",
            DeprecationWarning, stacklevel=2)
        _resource.ForbiddenResource.__init__(self, *args, **kwargs)


__all__ = [
    'Error', 'PageRedirect', 'InfiniteRedirection',
    'ErrorPage', 'NoResource', 'ForbiddenResource']
