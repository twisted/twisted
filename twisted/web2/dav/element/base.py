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
WebDAV XML base classes.

This module provides XML utilities for use with WebDAV.

See RFC 2518: http://www.ietf.org/rfc/rfc2518.txt (WebDAV)
"""

__all__ = [
    "dav_namespace",
    "WebDAVElement",
    "PCDATAElement",
    "WebDAVOneShotElement",
    "WebDAVUnknownElement",
    "WebDAVEmptyElement",
    "WebDAVTextElement",
    "WebDAVDateTimeElement",
    "DateTimeHeaderElement",    
]

import string
import StringIO
import xml.dom.minidom

import datetime

from twisted.python import log
from twisted.web2.http_headers import parseDateTime
from twisted.web2.dav.element.util import PrintXML, decodeXMLName

##
# Base XML elements
##

dav_namespace = "DAV:"

class WebDAVElement (object):
    """
    WebDAV XML element. (RFC 2518, section 12)
    """
    namespace          = dav_namespace # Element namespace (class variable)
    name               = None          # Element name (class variable)
    allowed_children   = None          # Types & count limits on child elements
    allowed_attributes = None          # Allowed attribute names
    hidden             = False         # Don't list in PROPFIND with <allprop>
    protected          = False         # See RFC 3253 section 1.4.1
    unregistered       = False         # Subclass of factory; doesn't register

    def qname(self):
        return (self.namespace, self.name)

    def sname(self):
        return "{%s}%s" % (self.namespace, self.name)

    qname = classmethod(qname)
    sname = classmethod(sname)

    def __init__(self, *children, **attributes):
        super(WebDAVElement, self).__init__()

        if self.allowed_children is None:
            raise NotImplementedError("WebDAVElement subclass %s is not implemented."
                                      % (self.__class__.__name__,))

        #
        # Validate that children are of acceptable types
        #
        allowed_children = dict([
            (child_type, list(limits))
            for child_type, limits
            in self.allowed_children.items()
        ])

        my_children = []

        for child in children:
            if child is None:
                continue

            if isinstance(child, (str, unicode)):
                child = PCDATAElement(child)

            assert isinstance(child, (WebDAVElement, PCDATAElement)), "Not an element: %r" % (child,)

            for allowed, (min, max) in allowed_children.items():
                if type(allowed) == type and isinstance(child, allowed):
                    qname = allowed
                elif child.qname() == allowed:
                    qname = allowed
                else:
                    continue

                if min is not None and min > 0:
                    min -= 1
                if max is not None:
                    assert max > 0, "Too many children of type %s for %s" % (child.sname(), self.sname())
                    max -= 1
                allowed_children[qname] = (min, max)
                my_children.append(child)
                break
            else:
                if not (isinstance(child, PCDATAElement) and child.isWhitespace()):
                    log.msg("Child of type %s is unexpected and therefore ignored in %s element"
                            % (child.sname(), self.sname()))

        for qname, (min, max) in allowed_children.items():
            if min != 0:
                raise ValueError("Not enough children of type {%s}%s for %s"
                                 % (qname[0], qname[1], self.sname()))

        self.children = tuple(my_children)

        #
        # Validate that attributes have known names
        #
        my_attributes = {}

        if self.allowed_attributes:
            for name in attributes:
                if name in self.allowed_attributes:
                    my_attributes[name] = attributes[name]
                else:
                    log.msg("Attribute %s is unexpected and therefore ignored in %s element"
                            % (name, self.sname()))
    
            for name, required in self.allowed_attributes.items():
                if required and name not in my_attributes:
                    raise ValueError("Attribute %s is required in %s element"
                                     % (name, self.sname()))

        elif not isinstance(self, WebDAVUnknownElement):
            if attributes:
                log.msg("Attributes %s are unexpected and therefore ignored in %s element"
                        % (attributes.keys(), self.sname()))

        self.attributes = my_attributes

    def __str__(self):
        return self.sname()

    def __repr__(self):
        if hasattr(self, "attributes") and hasattr(self, "children"):
            return "<%s %r: %r>" % (self.sname(), self.attributes, self.children)
        else:
            return "<%s>" % (self.sname())

    def __eq__(self, other):
        if isinstance(other, WebDAVElement):
            return (
                self.name       == other.name       and
                self.namespace  == other.namespace  and
                self.attributes == other.attributes and
                self.children   == other.children
            )
        else:
            return NotImplemented

    def __ne__(self, other):
        return not self.__eq__(other)

    def __contains__(self, child):
        return child in self.children

    def writeXML(self, output):
        document = xml.dom.minidom.Document()
        self.addToDOM(document, None)
        PrintXML(document, stream=output)

    def toxml(self):
        output = StringIO.StringIO()
        self.writeXML(output)
        return output.getvalue()

    def element(self, document):
        element = document.createElementNS(self.namespace, self.name)
        if hasattr(self, "attributes"):
            for name, value in self.attributes.items():
                namespace, name = decodeXMLName(name)
                attribute = document.createAttributeNS(namespace, name)
                attribute.nodeValue = value
                element.setAttributeNodeNS(attribute)
        return element

    def addToDOM(self, document, parent):
        element = self.element(document)

        if parent is None:
            document.appendChild(element)
        else:
            parent.appendChild(element)

        for child in self.children:
            if child:
                try:
                    child.addToDOM(document, element)
                except:
                    log.err("Unable to add child %r of element %s to DOM" % (child, self))
                    raise

    def childrenOfType(self, child_type):
        """
        Returns a list of children with the same qname as the given type.
        """
        if type(child_type) is tuple:
            qname = child_type
        else:
            qname = child_type.qname()

        return [ c for c in self.children if c.qname() == qname ]

    def childOfType(self, child_type):
        """
        Returns a child of the given type, if any, or None.
        Raises ValueError if more than one is found.
        """
        found = None
        for child in self.childrenOfType(child_type):
            if found:
                raise ValueError("Multiple %s elements found in %s" % (child_type.sname(), self.toxml()))
            found = child
        return found

class PCDATAElement (object):
    def sname(self): return "#PCDATA"

    qname = classmethod(sname)
    sname = classmethod(sname)

    def __init__(self, data):
        super(PCDATAElement, self).__init__()

        if data is None:
            data = ""
        elif type(data) is unicode:
            data = data.encode("utf-8")
        else:
            assert type(data) is str, ("PCDATA must be a string: %r" % (data,))

        self.data = data

    def __str__(self):
        return str(self.data)

    def __repr__(self):
        return "<%s: %r>" % (self.__class__.__name__, self.data)

    def __add__(self, other):
        if isinstance(other, PCDATAElement):
            return self.__class__(self.data + other.data)
        else:
            return self.__class__(self.data + other)

    def __eq__(self, other):
        if isinstance(other, PCDATAElement):
            return self.data == other.data
        elif type(other) in (str, unicode):
            return self.data == other
        else:
            return NotImplemented

    def __ne__(self, other):
        return not self.__eq__(other)

    def isWhitespace(self):
        for char in str(self):
            if char not in string.whitespace:
                return False
        return True

    def element(self, document):
        return document.createTextNode(self.data)

    def addToDOM(self, document, parent):
        try:
            parent.appendChild(self.element(document))
        except TypeError:
            log.err("Invalid PCDATA: %r" % (self.data,))
            raise

class WebDAVOneShotElement (WebDAVElement):
    """
    Element with exactly one WebDAVEmptyElement child and no attributes.
    """
    __singletons = {}

    def __new__(clazz, *children):
        child = None
        for next in children:
            if isinstance(next, WebDAVEmptyElement):
                if child is not None:
                    raise ValueError("%s must have exactly one child, not %r"
                                     % (clazz.__name__, children))
                child = next
            elif isinstance(next, PCDATAElement):
                pass
            else:
                raise ValueError("%s child is not a WebDAVEmptyElement instance: %s"
                                 % (clazz.__name__, next))

        if clazz not in WebDAVOneShotElement.__singletons:
            WebDAVOneShotElement.__singletons[clazz] = {
                child: WebDAVElement.__new__(clazz, children)
            }
        elif child not in WebDAVOneShotElement.__singletons[clazz]:
            WebDAVOneShotElement.__singletons[clazz][child] = (
                WebDAVElement.__new__(clazz, children)
            )

        return WebDAVOneShotElement.__singletons[clazz][child]

class WebDAVUnknownElement (WebDAVElement):
    """
    Placeholder for unknown element tag names.
    """
    allowed_children = {
        WebDAVElement: (0, None),
        PCDATAElement: (0, None),
    }

class WebDAVEmptyElement (WebDAVElement):
    """
    WebDAV element with no contents.
    """
    __singletons = {}

    def __new__(clazz, *args, **kwargs):
        assert not args

        if kwargs:
            return WebDAVElement.__new__(clazz, **kwargs)
        else:
            if clazz not in WebDAVEmptyElement.__singletons:
                WebDAVEmptyElement.__singletons[clazz] = (WebDAVElement.__new__(clazz))
            return WebDAVEmptyElement.__singletons[clazz]

    allowed_children = {}

    children = ()

class WebDAVTextElement (WebDAVElement):
    """
    WebDAV element containing PCDATA.
    """
    def fromString(clazz, string):
        if string is None:
            return clazz()
        elif isinstance(string, (str, unicode)):
            return clazz(PCDATAElement(string))
        else:
            return clazz(PCDATAElement(str(string)))

    fromString = classmethod(fromString)

    allowed_children = { PCDATAElement: (0, None) }

    def __str__(self):
        return "".join([c.data for c in self.children])

    def __repr__(self):
        content = str(self)
        if content:
            return "<%s: %r>" % (self.sname(), content)
        else:
            return "<%s>" % (self.sname(),)

    def __eq__(self, other):
        if isinstance(other, WebDAVTextElement):
            return str(self) == str(other)
        elif type(other) in (str, unicode):
            return str(self) == other
        else:
            return NotImplemented

class WebDAVDateTimeElement (WebDAVTextElement):
    """
    WebDAV date-time element. (RFC 2518, section 23.2)
    """
    def fromDate(clazz, date):
        """
        date may be a datetime.datetime instance, a POSIX timestamp
        (integer value, such as returned by time.time()), or an ISO
        8601-formatted (eg. "2005-06-13T16:14:11Z") date/time string.
        """
        def isoformat(date):
            if date.utcoffset() is None:
                return date.isoformat() + "Z"
            else:
                return date.isoformat()

        if type(date) is int:
            date = isoformat(datetime.datetime.fromtimestamp(date))
        elif type(date) is str:
            pass
        elif type(date) is unicode:
            date = date.encode("utf-8")
        elif isinstance(date, datetime.datetime):
            date = isoformat(date)
        else:
            raise ValueError("Unknown date type: %r" % (date,))

        return clazz(PCDATAElement(date))

    fromDate = classmethod(fromDate)

    def __init__(self, *children, **attributes):
        super(WebDAVDateTimeElement, self).__init__(*children, **attributes)
        self.datetime() # Raise ValueError if the format is wrong

    def __eq__(self, other):
        if isinstance(other, WebDAVDateTimeElement):
            return self.datetime() == other.datetime()
        else:
            return NotImplemented

    def datetime(self):
        s = str(self)
        if not s:
            return None
        else:
            return parse_date(s)

class DateTimeHeaderElement (WebDAVTextElement):
    """
    WebDAV date-time element for elements that substitute for HTTP
    headers. (RFC 2068, section 3.3.1)
    """
    def fromDate(clazz, date):
        """
        date may be a datetime.datetime instance, a POSIX timestamp
        (integer value, such as returned by time.time()), or an RFC
        2068 Full Date (eg. "Mon, 23 May 2005 04:52:22 GMT") string.
        """
        def format(date):
            #
            # FIXME: strftime() is subject to localization nonsense; we need to
            # ensure that we're using the correct localization, or don't use
            # strftime().
            #
            return date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        if type(date) is int:
            date = format(datetime.datetime.fromtimestamp(date))
        elif type(date) is str:
            pass
        elif type(date) is unicode:
            date = date.encode("utf-8")
        elif isinstance(date, datetime.datetime):
            if date.tzinfo:
                raise NotImplementedError("I need to normalize to UTC")
            date = format(date)
        else:
            raise ValueError("Unknown date type: %r" % (date,))

        return clazz(PCDATAElement(date))

    fromDate = classmethod(fromDate)

    def __init__(self, *children, **attributes):
        super(DateTimeHeaderElement, self).__init__(*children, **attributes)
        self.datetime() # Raise ValueError if the format is wrong

    def __eq__(self, other):
        if isinstance(other, WebDAVDateTimeElement):
            return self.datetime() == other.datetime()
        else:
            return NotImplemented

    def datetime(self):
        s = str(self)
        if not s:
            return None
        else:
            return parseDateTime(s)

##
# Utilities
##

class FixedOffset (datetime.tzinfo):
    """
    Fixed offset in minutes east from UTC.
    """
    def __init__(self, offset, name=None):
        super(FixedOffset, self).__init__()

        self._offset = datetime.timedelta(minutes=offset)
        self._name   = name

    def utcoffset(self, dt): return self._offset
    def tzname   (self, dt): return self._name
    def dst      (self, dt): return datetime.timedelta(0)

def parse_date(date):
    """
    Parse an ISO 8601 date and return a corresponding datetime.datetime object.
    """
    # See http://www.iso.org/iso/en/prods-services/popstds/datesandtime.html

    global regex_date

    if regex_date is None:
        import re

        regex_date = re.compile(
            "^" +
              "(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T" +
              "(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})(?:.(?P<subsecond>\d+))*" +
              "(?:Z|(?P<offset_sign>\+|-)(?P<offset_hour>\d{2}):(?P<offset_minute>\d{2}))" +
            "$"
        )

    match = regex_date.match(date)
    if match is not None:
        subsecond = match.group("subsecond")
        if subsecond is None:
            subsecond = 0
        else:
            subsecond = int(subsecond)

        offset_sign = match.group("offset_sign")
        if offset_sign is None:
            offset = FixedOffset(0)
        else:
            offset_hour   = int(match.group("offset_hour"  ))
            offset_minute = int(match.group("offset_minute"))

            delta = (offset_hour * 60) + offset_minute

            if   offset_sign == "+": offset = FixedOffset(0 - delta)
            elif offset_sign == "-": offset = FixedOffset(0 + delta)

        return datetime.datetime(
            int(match.group("year"  )),
            int(match.group("month" )),
            int(match.group("day"   )),
            int(match.group("hour"  )),
            int(match.group("minute")),
            int(match.group("second")),
            subsecond,
            offset
        )
    else:
        raise ValueError("Invalid ISO 8601 date format: %r" % (date,))

regex_date = None
