# -*- test-case-name: twisted.web.test -*-
# Copyright (c) 2001-2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Exception definitions for L{twisted.web}.
"""

import operator, warnings

from twisted.web import http


class Error(Exception):
    def __init__(self, code, message=None, response=None):
        """
        Initializes a basic exception.

        @param code: Refers to an HTTP status code for example http.NOT_FOUND.
        If no message is given the given code is mapped to a descriptive
        string and used instead.
        """

        message = message or http.responses.get(code)
        Exception.__init__(self, code, message, response)
        self.status = code
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
        message = message or ("%s to %s" % (http.responses.get(code), location))
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
        message = message or ("%s to %s" % (http.responses.get(code), location))
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
