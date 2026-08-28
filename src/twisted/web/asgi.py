import attr

from twisted.internet import defer
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET


class Q:
    def __init__(self):
        self.deferreds = []

        self._add()

    @property
    def deferred(self):
        return self.deferreds[0]

    def _add(self):
        self.deferreds.append(defer.Deferred())

    def add(self, item):
        if not self.deferreds[-1].called:
            self.deferreds[-1].callback(item)
        else:
            self.deferreds.append(defer.Deferred())
            self.deferreds[-1].callback(item)


@attr.s
class ASGIResource(Resource):
    _application = attr.ib()

    def render(self, request):
        queue = Q()

        scope = {
            "type": "http",
            "http_version": request.clientproto.split(b"/")[-1].decode("ascii"),
            "method": request.method.decode("ascii"),
            "scheme": "https" if request.isSecure() else "http",
        }

        def _finish(res):
            async def _():
                queue.add({"type": "http.disconnect"})

            return defer.ensureDeferred(_())

        request.notifyFinish().addCallback(_finish)

        async def write(content):
            if content["type"] == "http.response.start":
                request.setResponseCode(content["status"])
                for key, val in content.get("headers", []):
                    request.setHeader(key, val)

            elif content["type"] == "http.response.body":
                request.write(content["body"])
                if not content.get("more_body", False):
                    request.finish()

        app = self._application(scope)

        async def read():
            print(queue.deferred)
            res = await queue.deferred
            return res

        async def _run():
            await app(read, write)

        requestMessage = {"type": "http.request", "body": request.content.read()}

        queue.add(requestMessage)

        d = defer.ensureDeferred(_run())

        return NOT_DONE_YET
