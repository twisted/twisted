
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am the Twisted.Web error resources and exceptions."""

#t.w imports
#from twisted.web2 import resource
from twisted.web2 import responsecode

class OldError(Exception):
    def __init__(self, code, message = None, response = None):
        message = message or responsecode.RESPONSES.get(code)
        Exception.__init__(self, code, message, response)
        self.code = code
        self.response = response
        
    def __str__(self):
        return '%s %s' % (self[0], self[1])

class PageRedirect(OldError):
    """A request that resulted in a responsecode.redirect """
    def __init__(self, code, message = None, response = None, location = None):
        message = message or ("%s to %s" % (responsecode.RESPONSES.get(code), location))
        Error.__init__(self, code, message, response)
        self.location = location

# class ErrorPage(resource.Resource):
#     def __init__(self, status, brief, detail):
#         resource.Resource.__init__(self)
#         self.code = status
#         self.brief = brief
#         self.detail = detail

#     def render(self, request):
#         request.setResponseCode(self.code)
#         return ("""<html>
#         <head><title>%s - %s</title></head>
#         <body><h1>%s</h1>
#             <p>%s</p>
#         </body></html>\n\n""" %
#                 (self.code, self.brief, self.brief, self.detail))

#     def getChild(self, chnam, request):
#         return self


# class NoResource(ErrorPage):
#     def __init__(self, message="Sorry. No luck finding that resource."):
#         ErrorPage.__init__(self, responsecode.NOT_FOUND,
#                            "No Such Resource",
#                            message)

# class ForbiddenResource(ErrorPage):
#     def __init__(self, message="Sorry, resource is forbidden."):
#         ErrorPage.__init__(self, responsecode.FORBIDDEN,
#                            "Forbidden Resource",
#                            message)

# 300 - Should include entity with choices
# 301 -
# 304 - Must include Date, ETag, Content-Location, Expires, Cache-Control, Vary.
# 
# 401 - Must include WWW-Authenticate.
# 405 - Must include Allow.
# 406 - Should include entity describing allowable characteristics
# 407 - Must include Proxy-Authenticate
# 413 - May  include Retry-After
# 416 - Should include Content-Range
# 503 - Should include Retry-After

class MethodNotAllowed(OldError):
    """Raised by a resource when faced with an unsupported request method.

    This exception's first argument MUST be a sequence of the methods the
    resource *does* support.
    """

    allowedMethods = ()

    def __init__(self, allowedMethods):
        if not operator.isSequenceType(allowedMethods):
            s = ("First argument must be a sequence of supported methodds, "
                 "but my first argument is not a sequence.")
            raise TypeError, s
        Error.__init__(self, responsecode.NOT_ALLOWED, allowedMethods)
        self.allowedMethods = allowedMethods
        
