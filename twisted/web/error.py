
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

"""I am the Twisted.Web error resources and exceptions."""

#t.w imports
import resource

from twisted.protocols import http

class Error(Exception):
    def __init__(self, code, message = None, response = None):
        message = message or http.responses.get(code)
        Exception.__init__(self, code, message, response)
        self.status = code

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
