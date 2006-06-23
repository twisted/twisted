# -*- test-case-name: twisted.web2.dav.test.test_prop.PROP.test_PROPPATCH -*-
##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

"""
WebDAV-aware static resources.
"""

__all__ = ["http_PROPPATCH"]

from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet.defer import deferredGenerator, waitForDeferred
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError, StatusResponse
from twisted.web2.dav import davxml
from twisted.web2.dav.http import MultiStatusResponse, PropertyStatusResponseQueue
from twisted.web2.dav.util import davXMLFromStream

def http_PROPPATCH(self, request):
    """
    Respond to a PROPPATCH request. (RFC 2518, section 8.2)
    """
    if not self.fp.exists():
        log.err("File not found: %s" % (self.fp.path,))
        raise HTTPError(responsecode.NOT_FOUND)

    #
    # Read request body
    #
    try:
        doc = waitForDeferred(davXMLFromStream(request.stream))
        yield doc
        doc = doc.getResult()
    except ValueError, e:
        log.err("Error while handling PROPPATCH body: %s" % (e,))
        raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, str(e)))

    if doc is None:
        error = "Request XML body is required."
        log.err(error)
        raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, error))

    #
    # Parse request
    #
    update = doc.root_element
    if not isinstance(update, davxml.PropertyUpdate):
        error = ("Request XML body must be a propertyupdate element."
                 % (davxml.PropertyUpdate.sname(),))
        log.err(error)
        raise HTTPError(StatusResponse(responsecode.BAD_REQUEST, error))

    responses = PropertyStatusResponseQueue("PROPPATCH", request.uri, responsecode.NO_CONTENT)
    undoActions = []
    gotError = False

    try:
        #
        # Update properties
        #
        for setOrRemove in update.children:
            assert len(setOrRemove.children) == 1

            container = setOrRemove.children[0]

            assert isinstance(container, davxml.PropertyContainer)

            properties = container.children

            def do(action, property):
                """
                Perform action(property, request) while maintaining an
                undo queue.
                """
                has = waitForDeferred(self.hasProperty(property, request))
                yield has
                has = has.getResult()

                if has:
                    oldProperty = waitForDeferred(self.readProperty(property, request))
                    yield oldProperty
                    oldProperty.getResult()

                    def undo():
                        return self.writeProperty(oldProperty, request)
                else:
                    def undo():
                        return self.removeProperty(property, request)

                try:
                    x = waitForDeferred(action(property, request))
                    yield x
                    x.getResult()
                except ValueError, e:
                    # Convert ValueError exception into HTTPError
                    responses.add(
                        Failure(exc_value=HTTPError(StatusResponse(responsecode.FORBIDDEN, str(e)))),
                        property
                    )
                    yield False
                    return
                except:
                    responses.add(Failure(), property)
                    yield False
                    return
                else:
                    responses.add(responsecode.OK, property)

                    # Only add undo action for those that succeed because those that fail will not have changed               
                    undoActions.append(undo)

                    yield True
                    return

            do = deferredGenerator(do)

            if isinstance(setOrRemove, davxml.Set):
                for property in properties:
                    ok = waitForDeferred(do(self.writeProperty, property))
                    yield ok
                    ok = ok.getResult()
                    if not ok:
                        gotError = True
            elif isinstance(setOrRemove, davxml.Remove):
                for property in properties:
                    ok = waitForDeferred(do(self.removeProperty, property))
                    yield ok
                    ok = ok.getResult()
                    if not ok:
                        gotError = True
            else:
                raise AssertionError("Unknown child of PropertyUpdate: %s" % (setOrRemove,))
    except:
        #
        # If there is an error, we have to back out whatever we have
        # operations we have done because PROPPATCH is an
        # all-or-nothing request.
        # We handle the first one here, and then re-raise to handle the
        # rest in the containing scope.
        #
        for action in undoActions:
            x = waitForDeferred(action())
            yield x
            x.getResult()
        raise

    #
    # If we had an error we need to undo any changes that did succeed and change status of
    # those to 424 Failed Dependency.
    #
    if gotError:
        for action in undoActions:
            x = waitForDeferred(action())
            yield x
            x.getResult()
        responses.error()

    #
    # Return response
    #
    yield MultiStatusResponse([responses.response()])

http_PROPPATCH = deferredGenerator(http_PROPPATCH)
