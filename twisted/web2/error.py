# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Default error output filter for twisted.web2.
"""

from twisted.web2 import stream, http_headers
from twisted.web2.responsecode import *

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

ERROR_MESSAGES = {
    # 300
    # no MULTIPLE_CHOICES
    MOVED_PERMANENTLY: 'The document has permanently moved <a href="%(location)s">here</a>.',
    FOUND: 'The document has temporarily moved <a href="%(location)s">here</a>.',
    SEE_OTHER: 'The results are available <a href="%(location)s">here</a>.',
    # no NOT_MODIFIED
    USE_PROXY: "Access to this resource must be through the proxy %(location)s.",
    # 306 unused
    TEMPORARY_REDIRECT: 'The document has temporarily moved <a href="%(location)s">here</a>.',

    # 400
    BAD_REQUEST: "Your browser sent an invalid request.",
    UNAUTHORIZED: "You are not authorized to view the resource at %(uri)s. Perhaps you entered a wrong password, or perhaps your browser doesn't support authentication.",
    PAYMENT_REQUIRED: "Payment Required (useful result code, this...).",
    FORBIDDEN: "You don't have permission to access %(uri)s.",
    NOT_FOUND: "The resource %(uri)s cannot be found.",
    NOT_ALLOWED: "The requested method %(method)s is not supported by %(uri)s.",
    NOT_ACCEPTABLE: "No representation of %(uri)s that is acceptable to your client could be found.",
    PROXY_AUTH_REQUIRED: "You are not authorized to view the resource at %(uri)s. Perhaps you entered a wrong password, or perhaps your browser doesn't support authentication.",
    REQUEST_TIMEOUT: "Server timed out waiting for your client to finish sending the HTTP request.",
    CONFLICT: "Conflict (?)",
    GONE: "The resource %(uri)s has been permanently removed.",
    LENGTH_REQUIRED: "The resource %(uri)s requires a Content-Length header.",
    PRECONDITION_FAILED: "A precondition evaluated to false.",
    REQUEST_ENTITY_TOO_LARGE: "The provided request entity data is too longer than the maximum for the method %(method)s at %(uri)s.",
    REQUEST_URI_TOO_LONG: "The request URL is longer than the maximum on this server.",
    UNSUPPORTED_MEDIA_TYPE: "The provided request data has a format not understood by the resource at %(uri)s.",
    REQUESTED_RANGE_NOT_SATISFIABLE: "None of the ranges given in the Range request header are satisfiable by the resource %(uri)s.",
    EXPECTATION_FAILED: "The server does support one of the expectations given in the Expect header.",

    # 500
    INTERNAL_SERVER_ERROR: "An internal error occurred trying to process your request. Sorry.",
    NOT_IMPLEMENTED: "Some functionality requested is not implemented on this server.",
    BAD_GATEWAY: "An upstream server returned an invalid response.",
    SERVICE_UNAVAILABLE: "This server cannot service your request becaues it is overloaded.",
    GATEWAY_TIMEOUT: "An upstream server is not responding.",
    HTTP_VERSION_NOT_SUPPORTED: "HTTP Version not supported.",
    INSUFFICIENT_STORAGE_SPACE: "There is insufficient storage space available to perform that request.",
    NOT_EXTENDED: "This server does not support the a mandatory extension requested."
}

# Is there a good place to keep this function?
def _escape(original):
    if original is None:
        return None
    return original.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

def defaultErrorHandler(request, response):
    if response.stream is not None:
        # Already got an error message
        return response
    if response.code < 300:
        # We only do error messages
        return response
    
    message = ERROR_MESSAGES.get(response.code, None)
    if message is None:
        # No message specified for that code
        return response
    
    message = message % {
        'uri':_escape(request.uri),
        'location':_escape(response.headers.getHeader('location')),
        'method':_escape(request.method)
        }

    title = RESPONSES.get(response.code, "")
    body = ("<html><head><title>%d %s</title></head>"
            "<body><h1>%s</h1>%s</body></html>") % (
        response.code, title, title, message)
    
    response.headers.setHeader("content-type", http_headers.MimeType('text', 'html'))
    response.stream = stream.MemoryStream(body)
    
    return response
defaultErrorHandler.handleErrors = True


__all__ = ['defaultErrorHandler',]
