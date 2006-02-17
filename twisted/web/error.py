
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I am the Twisted.Web error resources and exceptions."""

#t.w imports
import resource

from twisted.web import http

class Error(Exception):
    def __init__(self, code, message = None, response = None):
        message = message or http.responses.get(code)
        Exception.__init__(self, code, message, response)
        self.status = code
        self.response = response
    
    def __str__(self):
        return '%s %s' % (self[0], self[1])

class PageRedirect(Error):
    """A request that resulted in a http redirect """
    def __init__(self, code, message = None, response = None, location = None):
        message = message or ("%s to %s" % (http.responses.get(code), location))
        Error.__init__(self, code, message, response)
        self.location = location

class ErrorPage(resource.Resource):
    def __init__(self, status, brief, detail):
        resource.Resource.__init__(self)
        self.code = status
        self.brief = brief
        self.detail = detail

    def render(self, request):
        request.setResponseCode(self.code)
        request.setHeader("content-type", "text/html")
        return ("""<html>
        <head><title>%s - %s</title></head>
        <body><h1>%s</h1>
            <p>%s</p>
        </body></html>\n\n""" %
                (self.code, self.brief, self.brief, self.detail))

    def getChild(self, chnam, request):
        return self


class NoResource(ErrorPage):
    def __init__(self, message="Sorry. No luck finding that resource."):
        ErrorPage.__init__(self, http.NOT_FOUND,
                           "No Such Resource",
                           message)

class ForbiddenResource(ErrorPage):
    def __init__(self, message="Sorry, resource is forbidden."):
        ErrorPage.__init__(self, http.FORBIDDEN,
                           "Forbidden Resource",
                           message)
