# -*- test-case-name: twisted.web.test.test_http_headers
# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An API for storing HTTP header names and values.
"""


def _dashCapitalize(name):
    """
    Return a string which is capitalized using '-' as a word separator.

    @param name: The name of the header to capitalize.
    @type name: str

    @return: The given header capitalized using '-' as a word separator.
    @rtype: str
    """
    return '-'.join([word.capitalize() for word in name.split('-')])



class _DictHeaders(object):
    """
    A C{dict}-like wrapper around L{Headers} to provide backwards compatibility
    for L{Request.received_headers} and L{Request.headers} which used to be
    plain C{dict} instances.

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


    def __cmp__(self, other):
        """
        Define comparison with C{dict} by comparing header names and the last
        value associated with each.
        """
        return cmp(self.copy(), other)


    def keys(self):
        """
        Return a list of all header names.
        """
        return [k.lower() for k, v in self._headers.getAllRawHeaders()]


    def iterkeys(self):
        """
        Return an iterable of all header names.
        """
        return iter(self.keys())


    def values(self):
        """
        Return a list of the last value for each header.
        """
        return [v[-1] for k, v in self._headers.getAllRawHeaders()]


    def itervalues(self):
        """
        Return an iterable of the last value for each header.
        """
        return iter(self.values())


    def items(self):
        """
        Return a list two-tuples of each lower-case header name and the last
        value for that header.
        """
        return [
            (k.lower(), v[-1]) for k, v in self._headers.getAllRawHeaders()]


    def iteritems(self):
        """
        Return an iterable of two-tuples of each lower-case header name and the
        last value for that header.
        """
        return iter(self.items())


    def clear(self):
        """
        Remove all headers.
        """
        self._headers._rawHeaders.clear()


    def copy(self):
        """
        Return a C{dict} mapping each header name to the last corresponding
        header value.
        """
        return dict(self.items())


    def get(self, name, default=None):
        """
        Return the last value associated with the given header.

        @type name: C{str}
        @param name: The name of the header for which to retrieve a value.

        @param default: The value to return if the given header is not present.

        @rtype: C{str}
        @return: The last header value for the named header.
        """
        values = self._headers.getRawHeaders(name)
        if values is not None:
            return values[-1]
        return default


    def has_key(self, name):
        """
        Return C{True} if the named header is present, C{False} otherwise.
        """
        return self._headers.getRawHeaders(name) is not None


    def __contains__(self, name):
        """
        Return C{True} if the named header is present, C{False} otherwise.
        """
        return self.has_key(name)


    _noDefault = object()
    def pop(self, name, default=_noDefault):
        """
        Remove the given header and return the last value associated with it.

        @type name: C{str}
        @param name: The name of the header for which to retrieve a value.

        @param default: The value to return if the given header is not present.

        @rtype: C{str}
        @return: The last header value for the named header.
        """
        values = self._headers.getRawHeaders(name)
        if values is not None:
            self._headers.removeHeader(name)
            return values[-1]
        if default is self._noDefault:
            raise KeyError(name)
        return default


    def popitem(self):
        """
        Remove and return one header name/value pair, returning only the last
        header value for headers with more than one.
        """
        name, values = self._headers._rawHeaders.popitem()
        return name, values[-1]


    def update(self, *args, **kw):
        """
        Add the given header name/value pairs to this object, replacing the
        values of any headers which are already present.
        """
        # Avoid having to replicate update logic exactly by using the real
        # implementation to do the work for us.
        helper = {}
        helper.update(*args, **kw)
        for k, v in helper.iteritems():
            self._headers.setRawHeaders(k, [v])


class Headers(object):
    """
    This class stores the HTTP headers as both a parsed representation
    and the raw string representation. It converts between the two on
    demand.

    @cvar _caseMappings: A C{dict} that maps lowercase header names
        to their canonicalized representation.

    @ivar _rawHeaders: A C{dict} mapping header names as C{str} to C{lists} of
        header values as C{str}.
    """
    _caseMappings = {'www-authenticate': 'WWW-Authenticate'}

    def __init__(self, rawHeaders=None):
        if rawHeaders is None:
            rawHeaders = {}
        self._rawHeaders = rawHeaders


    def __cmp__(self, other):
        """
        Define L{Headers} instances as being equal to each other if they have
        the same raw headers.
        """
        if isinstance(other, Headers):
            return cmp(self._rawHeaders, other._rawHeaders)
        return NotImplemented


    def hasHeader(self, name):
        """
        Check for the existence of a given header.

        @type name: C{str}
        @param name: The name of the HTTP header to check for.

        @rtype: C{bool}
        @return: C{True} if the header exists, otherwise C{False}.
        """
        return name.lower() in self._rawHeaders


    def removeHeader(self, name):
        """
        Remove the named header from this header object.

        @type name: C{str}
        @param name: The name of the HTTP header to remove.

        @return: C{None}
        """
        self._rawHeaders.pop(name.lower(), None)


    def setRawHeaders(self, name, values):
        """
        Sets the raw representation of the given header.

        @type name: C{str}
        @param name: The name of the HTTP header to set the values for.

        @type values: C{list}
        @param values: A list of strings each one being a header value of
            the given name.

        @return: C{None}
        """
        self._rawHeaders[name.lower()] = values


    def getRawHeaders(self, name, default=None):
        """
        Returns a list of headers matching the given name as the raw string
        given.

        @type name: C{str}
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
        for k, v in self._rawHeaders.iteritems():
            yield self._canonicalNameCaps(k), v


    def _canonicalNameCaps(self, name):
        """
        Return the canonical name for the given header.

        @type name: C{str}
        @param name: The all-lowercase header name to capitalize in its
            canonical form.

        @rtype: C{str}
        @return: The canonical name of the header.
        """
        return self._caseMappings.get(name, _dashCapitalize(name))
