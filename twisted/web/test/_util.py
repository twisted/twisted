# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
General helpers for L{twisted.web} unit tests.
"""

from twisted.internet.defer import succeed
from twisted.web import server


def _render(resource, request):
    result = resource.render(request)
    if isinstance(result, str):
        request.write(result)
        request.finish()
        return succeed(None)
    elif result is server.NOT_DONE_YET:
        if request.finished:
            return succeed(None)
        else:
            return request.notifyFinish()
    else:
        raise ValueError("Unexpected return value: %r" % (result,))
