from twisted.web.resource import Resource
from twisted.web import server
from twisted.internet import utils
from twisted.python import util

class FortuneResource(Resource):

    def render_GET(self, request):
        request.write("<pre>\n")
        deferred = utils.getProcessOutput("/usr/games/fortune")
        deferred.addCallback(lambda s:
                             (request.write(s+"\n"), request.finish()))
        deferred.addErrback(lambda s:
                     (request.write(str(s)), request.finish()))
        return server.NOT_DONE_YET

resource = FortuneResource()
