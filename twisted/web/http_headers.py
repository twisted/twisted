# -*- test-case-name: twisted.web.test.test_http_headers
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An API for storing HTTP header names and values.
"""

from __future__ import division, absolute_import

from collections import MutableMapping

from twisted.python.compat import comparable, cmp


def _dashCapitalize(name):
    """
    Return a byte string which is capitalized using '-' as a word separator.

    @param name: The name of the header to capitalize.
    @type name: C{bytes}

    @return: The given header capitalized using '-' as a word separator.
    @rtype: C{bytes}
    """
    return b'-'.join([word.capitalize() for word in name.split(b'-')])



class _DictHeaders(MutableMapping):
    """
    A C{dict}-like wrapper around L{Headers} to provide backwards compatibility
    for L{twisted.web.http.Request.received_headers} and
    L{twisted.web.http.Request.headers} which used to be plain C{dict}
    instances.

    @type _headers: L{Headers}
    @ivar _headers: The real header storage object.
    """
    def __init__(self, headers):
        self._headers = headers


    def __getitem__(self, key):
        """
        Return the last value for header of C{key}.
        """
        if self._headers.hasHeader(key):
            return self._headers.getRawHeaders(key)[-1]
        raise KeyError(key)


    def __setitem__(self, key, value):
        """
        Set the given header.
        """
        self._headers.setRawHeaders(key, [value])


    def __delitem__(self, key):
        """
        Delete the given header.
        """
        if self._headers.hasHeader(key):
            self._headers.removeHeader(key)
        else:
            raise KeyError(key)


    def __iter__(self):
        """
        Return an iterator of the lowercase name of each header present.
        """
        for k, v in self._headers.getAllRawHeaders():
            yield k.lower()


    def __len__(self):
        """
        Return the number of distinct headers present.
        """
        # XXX Too many _
        return len(self._headers._rawHeaders)


    # Extra methods that MutableMapping doesn't care about but that we do.
    def copy(self):
        """
        Return a C{dict} mapping each header name to the last corresponding
        header value.
        """
        return dict(self.items())


    def has_key(self, key):
        """
        Return C{True} if C{key} is a header in this collection, C{False}
        otherwise.
        """
        return key in self



@comparable
class Headers(object):
    """
    This class stores the HTTP headers as both a parsed representation
    and the raw string representation. It converts between the two on
    demand.

    @cvar _caseMappings: A C{dict} that maps lowercase header names
        to their canonicalized representation.

    @ivar _rawHeaders: A C{dict} mapping header names as C{bytes} to C{lists} of
        header values as C{bytes}.
    """
    _caseMappings = {
        b'content-md5': b'Content-MD5',
        b'dnt': b'DNT',
        b'etag': b'ETag',
        b'p3p': b'P3P',
        b'te': b'TE',
        b'www-authenticate': b'WWW-Authenticate',
        b'x-xss-protection': b'X-XSS-Protection'}

    def __init__(self, rawHeaders=None):
        self._rawHeaders = {}
        if rawHeaders is not None:
            for name, values in rawHeaders.items():
                self.setRawHeaders(name, values[:])


    def __repr__(self):
        """
        Return a string fully describing the headers set on this object.
        """
        return '%s(%r)' % (self.__class__.__name__, self._rawHeaders,)


    def __cmp__(self, other):
        """
        Define L{Headers} instances as being equal to each other if they have
        the same raw headers.
        """
        if isinstance(other, Headers):
            return cmp(
                sorted(self._rawHeaders.items()),
                sorted(other._rawHeaders.items()))
        return NotImplemented


    def copy(self):
        """
        Return a copy of itself with the same headers set.
        """
        return self.__class__(self._rawHeaders)


    def hasHeader(self, name):
        """
        Check for the existence of a given header.

        @type name: C{bytes}
        @param name: The name of the HTTP header to check for.

        @rtype: C{bool}
        @return: C{True} if the header exists, otherwise C{False}.
        """
        return name.lower() in self._rawHeaders


    def removeHeader(self, name):
        """
        Remove the named header from this header object.

        @type name: C{bytes}
        @param name: The name of the HTTP header to remove.

        @return: C{None}
        """
        self._rawHeaders.pop(name.lower(), None)


    def setRawHeaders(self, name, values):
        """
        Sets the raw representation of the given header.

        @type name: C{bytes}
        @param name: The name of the HTTP header to set the values for.

        @type values: C{list}
        @param values: A list of strings each one being a header value of
            the given name.

        @return: C{None}
        """
        if not isinstance(values, list):
            raise TypeError("Header entry %r should be list but found "
                            "instance of %r instead" % (name, type(values)))
        self._rawHeaders[name.lower()] = values


    def addRawHeader(self, name, value):
        """
        Add a new raw value for the given header.

        @type name: C{bytes}
        @param name: The name of the header for which to set the value.

        @type value: C{bytes}
        @param value: The value to set for the named header.
        """
        values = self.getRawHeaders(name)
        if values is None:
            self.setRawHeaders(name, [value])
        else:
            values.append(value)


    def getRawHeaders(self, name, default=None):
        """
        Returns a list of headers matching the given name as the raw string
        given.

        @type name: C{bytes}
        @param name: The name of the HTTP header to get the values of.

        @param default: The value to return if no header with the given C{name}
            exists.

        @rtype: C{list}
        @return: A C{list} of values for the given header.
        """
        return self._rawHeaders.get(name.lower(), default)


    def getAllRawHeaders(self):
        """
        Return an iterator of key, value pairs of all headers contained in this
        object, as strings.  The keys are capitalized in canonical
        capitalization.
        """
        for k, v in self._rawHeaders.items():
            yield self._canonicalNameCaps(k), v


    def _canonicalNameCaps(self, name):
        """
        Return the canonical name for the given header.

        @type name: C{bytes}
        @param name: The all-lowercase header name to capitalize in its
            canonical form.

        @rtype: C{bytes}
        @return: The canonical name of the header.
        """
        return self._caseMappings.get(name, _dashCapitalize(name))


__all__ = ['Headers']
