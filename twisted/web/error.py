"""I am the Twisted.Web error resources and exceptions."""

#t.w imports
import resource

from twisted import reality#.error

from twisted.protocols import http

class error(Exception):
    def __init__(self, code, message = None):
        message = message or http.responses.get(code)
        Exception.__init__(self, code, message)


class ErrorPage(resource.Resource):
    def __init__(self, status, brief, detail):
        resource.Resource.__init__(self)
        self.code = status
        self.brief = brief
        self.detail = detail

    def render(self, request):
        request.setResponseCode(self.code)
        return "<HTML><BODY><H1>%s</h1><p>%s</p></BODY></HTML>" % (self.brief, self.detail)

    def getChild(self, chnam, request):
        return self


class NoResource(ErrorPage):
    #reality.error instead of reality.
    def __init__(self, message=reality.NoVerb('web').format()):
        ErrorPage.__init__(self, http.NOT_FOUND,
                           "No Such Resource",
                           message)
