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
from twisted.web2 import responsecode
from twisted.web2.http import StatusResponse
from twisted.web2.dav import davxml
from twisted.web2.dav.http import ResponseQueue
from twisted.web2.dav.util import davXMLFromStream

def http_PROPPATCH(self, request):
    """
    Respond to a PROPPATCH request. (RFC 2518, section 8.2)
    """
    if not self.fp.exists():
        log.err("File not found: %s" % (self.fp.path,))
        return responsecode.NOT_FOUND

    #
    # Read request body
    #
    d = davXMLFromStream(request.stream)

    #
    # Set properties
    #
    def gotXML(doc):
        if doc is None:
            error = "Request XML body is required."
            log.err(error)
            return StatusResponse(responsecode.BAD_REQUEST, error)

        #
        # Parse request
        #
        update = doc.root_element
        if not isinstance(update, davxml.PropertyUpdate):
            error = ("Request XML body must be a propertyupdate element."
                     % (davxml.PropertyUpdate.sname(),))
            log.err(error)
            return StatusResponse(responsecode.BAD_REQUEST, error)

        responses = ResponseQueue(self.fp.path, "DELETE", responsecode.NO_CONTENT)
        undo_actions = []

        try:
            #
            # Update properties
            #
            for set_or_remove in update.children:
                assert len(set_or_remove.children) == 1

                container = set_or_remove.children[0]

                assert isinstance(container, davxml.PropertyContainer)

                properties = container.children

                def do(action, property):
                    #
                    # Perform action(property) while maintaining the undo
                    # queue.
                    #
                    if self.hasProperty(property):
                        old_property = self.readProperty(property)
                        def undo(): self.writeProperty(old_property)
                    else:
                        def undo(): self.removeProperty(property)

                    try:
                        action(property)
                    except:
                        responses.add(self.fp.path, Failure())
                    else:
                        responses.add(self.fp.path, responsecode.OK)                        

                    undo_actions.append(undo)

                if isinstance(set_or_remove, davxml.Set):
                    for property in properties:
                        do(self.writeProperty, property)
                elif isinstance(set_or_remove, davxml.Remove):
                    for property in properties:
                        do(self.removeProperty, property)
                else:
                    raise AssertionError("Unknown child of PropertyUpdate: %s"
                                         % (set_or_remove,))
        except:
            #
            # If there is an error, we have to back out whatever we have
            # operations we have done because PROPPATCH is an
            # all-or-nothing request.
            #
            for action in undo_actions: action()
            raise

        #
        # Return response
        #
        return responses.response()

    def gotError(f):
        log.err("Error while handling PROPPATCH body: %s" % (f,))

        # ValueError is raised on a bad request.  Re-raise others.
        f.trap(ValueError)

        return StatusResponse(responsecode.BAD_REQUEST, str(f))

    d.addCallback(gotXML)
    d.addErrback(gotError)

    return d
