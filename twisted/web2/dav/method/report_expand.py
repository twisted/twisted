# -*- test-case-name: twisted.web2.dav.test.test_report_expand -*-
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
WebDAV expand-property report
"""

__all__ = ["report_DAV__expand_property"]

from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet.defer import deferredGenerator, waitForDeferred
from twisted.web2 import responsecode
from twisted.web2.dav import davxml
from twisted.web2.dav.http import statusForFailure
from twisted.web2.dav.davxml import dav_namespace

def report_DAV__expand_property(self, request, expand_property):
    """
    Generate an expand-property REPORT. (RFC 3253, section 3.8)
    """
    # FIXME: Handle depth header

    if not isinstance(expand_property, davxml.ExpandProperty):
        raise ValueError("%s expected as root element, not %s."
                         % (davxml.ExpandProperty.sname(), expand_property.sname()))

    #
    # Expand DAV:allprop
    #
    properties = {}

    for property in expand_property.children:
        namespace = property.getAttribute("namespace")
        name      = property.getAttribute("name")

        if not namespace: namespace = dav_namespace

        if (namespace, name) == (dav_namespace, "allprop"):
            all_properties = waitForDeferred(self.listAllProp(request))
            yield all_properties
            all_properties = all_properties.getResult()

            for all_property in all_properties:
                properties[all_property.qname()] = property
        else:
            properties[(namespace, name)] = property

    #
    # Look up the requested properties
    #
    properties_by_status = {
        responsecode.OK        : [],
        responsecode.NOT_FOUND : [],
    }

    for property in properties:
        my_properties = waitForDeferred(self.listProperties(request))
        yield my_properties
        my_properties = my_properties.getResult()

        if property in my_properties:
            try:
                value = waitForDeferred(self.readProperty(property, request))
                yield value
                value = value.getResult()

                if isinstance(value, davxml.HRef):
                    raise NotImplementedError()
                else:
                    raise NotImplementedError()
            except:
                f = Failure()

                log.err("Error reading property %r for resource %s: %s"
                        % (property, self, f.value))

                status = statusForFailure(f, "getting property: %s" % (property,))
                if status not in properties_by_status:
                    properties_by_status[status] = []

                raise NotImplementedError()

                #properties_by_status[status].append(
                #    ____propertyName(property)
                #)
        else:
            log.err("Can't find property %r for resource %s" % (property, self))
            properties_by_status[responsecode.NOT_FOUND].append(property)

    raise NotImplementedError()

report_DAV__expand_property = deferredGenerator(report_DAV__expand_property)
