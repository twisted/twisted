# -*- test-case-name: twisted.web.test.test_http_headers
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An API for storing HTTP header names and values.
"""


from UserDict import DictMixin


def _dashCapitalize(name):
    """
    Return a string which is capitalized using '-' as a word separator.

    @param name: The name of the header to capitalize.
    @type name: str

    @return: The given header capitalized using '-' as a word separator.
    @rtype: str
    """
    return '-'.join([word.capitalize() for word in name.split('-')])



class _DictHeaders(DictMixin):
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


    def keys(self):
        """
        Return a list of all header names.
        """
        return [k.lower() for k, v in self._headers.getAllRawHeaders()]


    def copy(self):
        """
        Return a C{dict} mapping each header name to the last corresponding
        header value.
        """
        return dict(self.items())


    # Python 2.3 DictMixin.setdefault is defined so as not to have a default
    # for the value parameter.  This is necessary to make this setdefault look
    # like dict.setdefault on Python 2.3. -exarkun
    def setdefault(self, name, value=None):
        """
        Retrieve the last value for the given header name.  If there are no
        values present for that header, set the value to C{value} and return
        that instead.  Note that C{None} is the default for C{value} for
        backwards compatibility, but header values may only be of type C{str}.
        """
        return DictMixin.setdefault(self, name, value)


    # The remaining methods are only for efficiency.  The same behavior
    # should remain even if they are removed.  For details, see
    # <http://docs.python.org/lib/module-UserDict.html>.
    # -exarkun
    def __contains__(self, name):
        """
        Return C{True} if the named header is present, C{False} otherwise.
        """
        return self._headers.getRawHeaders(name) is not None


    def __iter__(self):
        """
        Return an iterator of the lowercase name of each header present.
        """
        for k, v in self._headers.getAllRawHeaders():
            yield k.lower()


    def iteritems(self):
        """
        Return an iterable of two-tuples of each lower-case header name and the
        last value for that header.
        """
        for k, v in self._headers.getAllRawHeaders():
            yield k.lower(), v[-1]



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
    _caseMappings = {
        'content-md5': 'Content-MD5',
        'dnt': 'DNT',
        'etag': 'ETag',
        'p3p': 'P3P',
        'te': 'TE',
        'www-authenticate': 'WWW-Authenticate',
        'x-xss-protection': 'X-XSS-Protection'}

    def __init__(self, rawHeaders=None):
        self._rawHeaders = {}
        if rawHeaders is not None:
            for name, values in rawHeaders.iteritems():
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
            return cmp(self._rawHeaders, other._rawHeaders)
        return NotImplemented


    def copy(self):
        """
        Return a copy of itself with the same headers set.
        """
        return self.__class__(self._rawHeaders)


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
        if not isinstance(values, list):
            raise TypeError("Header entry %r should be list but found "
                            "instance of %r instead" % (name, type(values)))
        self._rawHeaders[name.lower()] = values


    def addRawHeader(self, name, value):
        """
        Add a new raw value for the given header.

        @type name: C{str}
        @param name: The name of the header for which to set the value.

        @type value: C{str}
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


__all__ = ['Headers']
