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
WebDAV PROPFIND method
"""

__all__ = ["http_PROPFIND"]

from twisted.python import log
from twisted.python.failure import Failure
from twisted.web2 import responsecode
from twisted.web2.http import StatusResponse
from twisted.web2.dav import davxml
from twisted.web2.dav.http import MultiStatusResponse, statusForFailure
from twisted.web2.dav.util import normalizeURL, joinURL, davXMLFromStream

def http_PROPFIND(self, request):
    """
    Respond to a PROPFIND request. (RFC 2518, section 8.1)
    """
    self.fp.restat(False)

    if not self.fp.exists():
        log.err("File not found: %s" % (self.fp.path,))
        return responsecode.NOT_FOUND

    #
    # Read request body
    #
    d = davXMLFromStream(request.stream)

    def gotXML(doc):
        if doc is None:
            # No request body means get all properties.
            search_properties = "all"
        else:
            #
            # Parse request
            #
            find = doc.root_element
            if not isinstance(find, davxml.PropertyFind):
                error = ("Non-%s element in PROPFIND request body: %s"
                         % (davxml.PropertyFind.sname(), find))
                log.err(error)
                return StatusResponse(responsecode.BAD_REQUEST, error)

            container = find.children[0]

            assert isinstance(container, davxml.PropertyContainer)

            properties = container.children

            #
            # FIXME: Revisit AllProperties logic
            # - skip hidden props
            # - allprop combined with other (eg. non-hidden) props
            #
            if davxml.AllProperties() in properties:
                # Get all properties
                search_properties = "all"
            elif davxml.PropertyName() in properties:
                if len(properties) is not 1:
                    error = ("PROPFIND combines %s element with others: %s"
                             % (davxml.PropertyName.sname(), container))
                    log.err(error)
                    return StatusResponse(responsecode.BAD_REQUEST, error)

                # Get names only
                search_properties = "names"
            else:
                search_properties = [(p.namespace, p.name) for p in properties]

        #
        # Generate XML output stream
        #
        request_uri = request.uri
        depth = request.headers.getHeader("depth", "infinity")

        xml_responses = []

        resources = [(self, None)]
        resources.extend(self.getChildren(depth))

        for resource, uri in resources:
            if uri is None:
                uri = normalizeURL(request_uri)
                if self.isCollection: uri += "/"
            else:
                uri = joinURL(request_uri, uri)
        
            if search_properties is "names":
                properties_by_status = {
                    responsecode.OK: davxml.PropertyContainer(*[propertyName(p) for p in resource.properties])
                }
            else:
                properties_by_status = {
                    responsecode.OK        : [],
                    responsecode.NOT_FOUND : [],
                }

                resource_properties = resource.properties

                if search_properties is "all":
                    search_properties = resource_properties.keys()
        
                for property in search_properties:
                    if property in resource_properties:
                        try:
                            properties_by_status[responsecode.OK].append(resource_properties[property])
                        except:
                            f = Failure()

                            log.err("Error reading property %r for resource %s: %s" % (property, uri, f.value))

                            status = statusForFailure(f, "getting property: %s" % (property,))
                            if status not in properties_by_status:
                                properties_by_status[status] = []
                            properties_by_status[status].append(propertyName(property))
                    else:
                        log.err("Can't find property %r for resource %s" % (property, uri))
                        properties_by_status[responsecode.NOT_FOUND].append(propertyName(property))

            propstats = []

            for status in properties_by_status:
                properties = properties_by_status[status]
                if not properties: continue

                xml_status    = davxml.Status.fromResponseCode(status)
                xml_container = davxml.PropertyContainer(*properties)
                xml_propstat  = davxml.PropertyStatus(xml_container, xml_status)

                propstats.append(xml_propstat)

            xml_resource = davxml.HRef.fromString(uri)
            xml_response = davxml.PropertyStatusResponse(xml_resource, *propstats)

            xml_responses.append(xml_response)

        #
        # Return response
        #
        return MultiStatusResponse(xml_responses)

    def gotError(f):
        log.err("Error while handling PROPFIND body: %s" % (f,))

        # ValueError is raised on a bad request.  Re-raise others.
        f.trap(ValueError)

        return StatusResponse(responsecode.BAD_REQUEST, str(f))

    d.addCallback(gotXML)
    d.addErrback(gotError)

    return d

##
# Utilities
##

def propertyName(name):
    property_namespace, property_name = name
    class PropertyName (davxml.WebDAVEmptyElement):
        namespace = property_namespace
        name = property_name
    return PropertyName()
