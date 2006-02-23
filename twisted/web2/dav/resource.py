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
web2.dav interfaces.
"""

__all__ = ["DAVPropertyMixIn", "DAVMetaDataMixin"]

from twisted.python import log
from twisted.web2 import responsecode
from twisted.web2.http import HTTPError
from twisted.web2.static import MetaDataMixin
from twisted.web2.dav import davxml
from twisted.web2.dav.props import WebDAVPropertyStore

class DAVPropertyMixIn(MetaDataMixin):
    """
    Mix-in class which implements the DAV property access API in
    L{IDAVResource}.
    """
    def getProperties(self):
        """
        Provides internal access to the WebDAV property store.  You probably
        shouldn't be calling this directly if you can use the property accessors
        in the IDAVResource API instead.  However, a subclass may chose to
        override this method to provide it's own property store.

        Note that this property store contains both dead and live properties;
        live properties are often not writeable, whereas dead properties usually
        are (assuming you have permission).

        This implementation uses a L{twisted.web2.dav.WebDAVPropertyStore} which
        is constructed with the dead property store returned by
        L{getDeadProperties}.

        @return: a dict-like object from which one can read and to which one can
            write properties.  Keys are qname tuples (ie. C{(namespace, name)})
            as returned by L{davxml.WebDAVElement.qname()} and values are
            L{davxml.WebDAVElement} instances.
        """
        if not hasattr(self, "_properties"):
            self._properties = WebDAVPropertyStore(self, self.getDeadProperties())
        return self._properties

    def getDeadProperties(self):
        """
        Provides internal access to the WebDAV dead property store.  You
        probably shouldn't be calling this directly if you can use the property
        accessors in the L{IDAVResource} API instead.  However, a subclass must
        override this method to provide it's own dead property store.

        This implementation raises L{NotImplementedError}.

        @return: a dict-like object from which one can read and to which one can
            write dead properties.  Keys are qname tuples (ie. C{(namespace, name)})
            as returned by L{davxml.WebDAVElement.qname()} and values are
            L{davxml.WebDAVElement} instances.
        """
        raise NotImplementedError("Subclass must implement getDeadProperties()")

    def hasProperty(self, property):
        """
        See L{IDAVResource.hasProperty}.
        """
        return (property.qname() in self.getProperties())

    def readProperty(self, property):
        """
        See L{IDAVResource.readProperty}.
        """
        try:
            return self.getProperties()[property.qname()]
        except KeyError:
            log.err("No such property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)

    def writeProperty(self, property):
        """
        See L{IDAVResource.writeProperty}.
        """
        try:
            self.getProperties()[property.qname()] = property
        except ValueError:
            log.err("Read-only property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)

    def removeProperty(self, property):
        """
        See L{IDAVResource.removeProperty}.
        """
        try:
            del(self.getProperties()[property.qname()])
        except ValueError:
            log.err("Read-only property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)
        except KeyError:
            log.err("No such property %s" % (property.sname(),))
            raise HTTPError(responsecode.CONFLICT)

    #
    # Overrides some methods in MetaDataMixin in order to allow DAV properties
    # to override the values of some HTTP metadata.
    #
    def contentType(self):
        if (davxml.dav_namespace, "getcontenttype") in self.getDeadProperties():
            return self.getDeadProperties()[(davxml.dav_namespace, "getcontenttype")].mimeType()
        else:
            return super(DAVPropertyMixIn, self).contentType()

    def displayName(self):
        if (davxml.dav_namespace, "displayname") in self.getDeadProperties():
            return str(self.getDeadProperties()[(davxml.dav_namespace, "displayname")])
        else:
            return super(DAVPropertyMixIn, self).displayName()
