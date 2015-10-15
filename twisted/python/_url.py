# -*- test-case-name: twisted.python.test.test_url -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
URL parsing, construction and rendering.
"""

from urlparse import urlsplit, urlunsplit
from urllib import quote as urlquote, unquote as urlunquote
from unicodedata import normalize

# RFC 3986 section 2.2, Reserved Characters
_genDelims = u':/?#[]@'
_subDelims = u"!$&'()*+,;="

_validEverywhere = u'-._~'
_validInPath = _subDelims + u':@'
_validInFragment = _validInPath + u'/?'
_validInQuery = (_validInFragment
                 .replace(u'&', u'').replace(u'=', u'').replace(u'+', u''))


def _minimalPercentEncode(text, safe):
    """
    Percent-encode only the characters that are syntactically necessary for
    serialization, preserving any IRI-style textual data.

    @param text: the text to escaped
    @type text: L{unicode}

    @param safe: characters safe to include in the return value
    @type safe: L{unicode}

    @return: the encoded version of C{text}
    @rtype: L{unicode}
    """
    unsafe = set(_genDelims + _subDelims) - set(safe)
    return u''.join((c if c not in unsafe else "%{:02X}".format(ord(c)))
                    for c in text)



def _maximalPercentEncode(text, safe):
    """
    Percent-encode everything required to convert a portion of an IRI to a
    portion of a URI.

    @param text: the text to encode.
    @type text: L{unicode}

    @param safe: a string of safe characters.
    @type safe: L{unicode}

    @return: the encoded version of C{text}
    @rtype: L{unicode}
    """
    return urlquote(
        normalize("NFC", text).encode("utf-8"), safe.encode("ascii")
    ).decode("ascii")



def _percentDecode(text):
    """
    Replace percent-encoded characters with their UTF-8 equivalents.

    @param text: The text with percent-encoded UTF-8 in it.
    @type text: L{unicode}

    @return: the encoded version of C{text}
    @rtype: L{unicode}
    """
    return urlunquote(text.encode("ascii")).decode("utf-8")



def _resolveDotSegments(pathSegments):
    """
    Normalise the URL path by resolving segments of '.' and '..'.

    @param pathSegments: list of path segments

    @see: RFC 3986 section 5.2.4, Remove Dot Segments

    @return: a new L{list} of path segments with the '.' and '..' elements
        removed and resolved.
    """
    segs = []

    for seg in pathSegments:
        if seg == u'.':
            pass
        elif seg == u'..':
            if segs:
                segs.pop()
        else:
            segs.append(seg)

    if list(pathSegments[-1:]) in ([u'.'], [u'..']):
        segs.append(u'')

    return segs



def _checkUnicodeOrNone(s):
    """
    Check if the given parameter is unicode, allowing None as well.

    @param s: The parameter to check.

    @raise TypeError: if C{s} is C{None} or an instance of L{unicode}.

    @return: C{s}
    """
    if not isinstance(s, (unicode, None.__class__)):
        raise TypeError("%r is not unicode" % (s,))
    return s



def _maybe(f, x):
    """
    Call C{f} on C{x} if C{x} is not None.

    @param f: a 1-argument callable taking C{x} and returning something

    @param x: a value (or C{None})

    @return: C{f(x)} or C{None}.
    """
    if x is not None:
        return f(x)



_unspecified = object()

def _optional(argument, default):
    """
    If the given value is C{_unspecified}, return C{default}; otherwise return
    C{argument}.

    @param argument: The argument passed.

    @param default: The default to use if C{argument} is C{_unspecified}.

    @return: C{argument} or C{default}
    """
    if argument is _unspecified:
        return default
    else:
        return argument

_schemeDefaultPorts = {
    u'http': 80,
    u'https': 443,
}


class Query(object):
    """
    A L{Query} represents the query portion of a L{URL}; the part after the
    C{?}.
    """

    def __init__(self, url):
        """
        Construct a L{Query} from a L{URL}.
        """
        self._url = url


    def add(self, name, value=None):
        """
        Add a query argument with the given value None indicates that the
        argument has no value.

        @param name: The name (the part before the C{=}) of the query parameter
            to add.

        @param value: The value (the part after the C{=}) of the query
            parameter to add.

        @return: a new L{URL} with the parameter added.
        """
        _checkUnicodeOrNone(name)
        _checkUnicodeOrNone(value)

        return self._url.replace(
            queryParameters=self._url.queryParameters + ((name, value),)
        )


    def set(self, name, value=None):
        """
        Remove all existing occurrences of the query argument 'name', *if it
        exists*, then add the argument with the given value.

        C{None} indicates that the argument has no value.

        @param name: The name (the part before the C{=}) of the query parameter
            to add.

        @param value: The value (the part after the C{=}) of the query
            parameter to add.

        @return: a new L{URL} with the parameter added or changed.
        """
        if (not isinstance(name, unicode) or
            not isinstance(value, (unicode, None.__class__))):
            raise TypeError("name and value must be unicode.")
        # Preserve the original position of the query key in the list
        i = 0
        for (k, v) in self._url.queryParameters:
            if k == name:
                break
            i += 1
        q = list(filter(lambda x: x[0] != name, self._url.queryParameters))
        q.insert(i, (name, value))
        return self._url.replace(queryParameters=q)


    def get(self, name):
        """
        Retrieve a list of values for the given named query parameter.

        @param name: The name of the query parameter to retrieve.

        @return: all the values associated with the key; for example, for the
            query string x=1&x=2, C{[u'1', u'2']}
        @rtype: L{list} of L{unicode}
        """
        return [value for (key, value) in self._url.queryParameters
                if name == key]


    def remove(self, name):
        """
        Remove all query arguments with the given name.

        @param name: The name of the query parameter to remove.

        @return: a new L{URL} with the parameter removed.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        return self._url.replace(filter(lambda x: x[0] != name,
                                   self._url.queryParameters))


    def clear(self):
        """
        Remove all existing query arguments.

        @return: a new L{URL} with the entire query string removed.
        """
        return self._url.replace(queryParameters=[])



class URL(object):
    """
    A L{URL} represents a URL and provides a convenient API for modifying its
    parts.

    A URL is split into a number of distinct parts: scheme, host, port, path
    segments, query parameters and fragment identifier::

        http://example.com:8080/a/b/c?d=e#f
        ^ scheme           ^ port     ^ query parameters
               ^ host           ^ path segments
                                         ^ fragment

    @see: U{RFC 3986, Uniform Resource Identifier (URI): Generic Syntax
        <https://tools.ietf.org/html/rfc3986>}
    @see: U{RFC 3987, Internationalized Resource Identifiers
        <https://tools.ietf.org/html/rfc3986>}

    @ivar scheme: The URI scheme.
    @type scheme: L{unicode}

    @ivar host: The host name.
    @type host: L{unicode}

    @ivar port: The port number.
    @type port: L{int}

    @ivar pathSegments: The path segments.
    @type pathSegments: L{tuple} of L{unicode}.

    @ivar queryParameters: The query parameters, as (name, value) pairs.
    @type queryParameters: L{tuple} of 2-L{tuple}s of (name: L{unicode}, value:
        (L{unicode} for values or C{None} for stand-alone query parameters with
        no C{=} in them)).

    @ivar fragment: The fragment identifier.
    @type fragment: L{unicode}

    @ivar rooted: Does the path start with a C{/}?  This is taken from the
        terminology in the BNF grammar, specifically the C{path-rootless},
        rule, since "absolute path" and "absolute URI" are somewhat ambiguous.
        C{pathSegments} does not contain the implicit prefixed C{"/"} since
        that is somewhat awkward to work with.
    @type rooted: L{bool}
    """

    def __init__(self, scheme=None, host=None, pathSegments=None,
                 queryParameters=None, fragment=None, port=None,
                 rooted=True):
        """
        Create a new L{URL} from structured information about itself.

        @ivar scheme: The URI scheme.
        @type scheme: L{unicode}

        @ivar host: The host portion of the netloc.
        @type host: L{unicode}

        @ivar port: The port number portion of the netloc.
        @type port: L{int}

        @ivar pathSegments: The path segments.
        @type pathSegments: Iterable of L{unicode}.

        @ivar queryParameters: The query parameters, as name-value pairs
        @type queryParameters: Iterable of pairs of L{unicode} (or C{None}, for
            values).

        @ivar fragment: The fragment identifier.
        @type fragment: L{unicode}

        @ivar rooted: Does the path start with a C{/}?  This is taken from the
            terminology in the BNF grammar, specifically the C{path-rootless},
            rule, since "absolute path" and "absolute URI" are somewhat
            ambiguous.  C{pathSegments} does not contain the implicit prefixed
            C{"/"} since that is somewhat awkward to work with.
        @type rooted: L{bool}
        """
        # Fall back to defaults.
        if pathSegments is None:
            pathSegments = [u'']
        if queryParameters is None:
            queryParameters = []
        if fragment is None:
            fragment = u''
        if host is not None and scheme is None:
            scheme = u'http'
        if port is None:
            port = _schemeDefaultPorts.get(scheme)

        # Set attributes.
        self._scheme = _checkUnicodeOrNone(scheme)
        self._host = _checkUnicodeOrNone(host)
        self._pathSegments = tuple(map(_checkUnicodeOrNone, pathSegments))
        self._queryParameters = tuple((_checkUnicodeOrNone(k),
                                       _checkUnicodeOrNone(v)) for (k, v) in
                                      queryParameters)
        self._fragment = _checkUnicodeOrNone(fragment)
        self._port = port
        self._rooted = rooted

    scheme = property(lambda self: self._scheme)
    host = property(lambda self: self._host)
    port = property(lambda self: self._port)
    pathSegments = property(lambda self: self._pathSegments)
    queryParameters = property(lambda self: self._queryParameters)
    fragment = property(lambda self: self._fragment)
    rooted = property(lambda self: self._rooted)


    def __eq__(self, other):
        """
        L{URL}s are equal to L{URL} objects that are structurally similar to
        themselves.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        for attr in ['scheme', 'host', 'pathSegments', 'queryParameters',
                     'fragment', 'port', 'rooted']:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True


    def __ne__(self, other):
        """
        L{URL}s are unequal (i.e. C{!=} is True) to L{URL} objects that are
        structurally similar to themselves.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        return not self.__eq__(other)


    @property
    def query(self):
        """
        Return an attribute with a structural API for manipulating query
        segments on this URL.
        """
        return Query(self)


    @property
    def absolute(self):
        """
        Is this URL complete enough to resolve a resource without resolution
        relative to a base-URI?
        """
        return bool(self.scheme and self.host and self.rooted)


    def replace(self, scheme=_unspecified, host=_unspecified,
                pathSegments=_unspecified, queryParameters=_unspecified,
                fragment=_unspecified, port=_unspecified,
                rooted=_unspecified):
        """
        Make a new instance of C{self.__class__}, passing along the given
        arguments to its constructor.

        @param scheme: the scheme of the new URL; if unspecified, the scheme of
            this URL.
        @type scheme: L{unicode}

        @param host: the host of the new URL; if unspecified, the host of this
            URL.
        @type host: L{unicode}

        @param pathSegments: the path segments of the new URL; if unspecified,
            the path segments of this URL.
        @type pathSegments: iterable of L{unicode}

        @param queryParameters: the query elements of the new URL; if
            unspecified, the query segments of this URL.
        @type queryParameters: iterable of 2-L{tuple}s of key, value.

        @param fragment: the fragment of the new URL; if unspecified, the query
            segments of this URL.
        @type fragment: L{unicode}

        @param port: the port of the new URL; if unspecified, the port of this
            URL.
        @type port: L{int}

        @param rooted: C{True} if the given C{pathSegments} are meant to start
            at the root of the host; C{False} otherwise.  Only meaningful for
            relative URIs.
        @type rooted: L{bool}

        @return: a new L{URL}.
        """
        return self.__class__(
            scheme=_optional(scheme, self.scheme),
            host=_optional(host, self.host),
            pathSegments=_optional(pathSegments, self.pathSegments),
            queryParameters=_optional(queryParameters, self.queryParameters),
            fragment=_optional(fragment, self.fragment),
            port=_optional(port, self.port),
            rooted=_optional(rooted, self.rooted)
        )


    @classmethod
    def fromText(cls, s):
        """
        Parse the given string into a URL object.

        Relative path references are not supported.

        @param s: a valid URI or IRI
        @type s: L{unicode}

        @return: the parsed representation of C{s}
        @rtype: L{URL}
        """
        (scheme, netloc, path, query, fragment) = [
            (u'' if x == b'' else x) for x in urlsplit(s)
        ]
        split = netloc.split(u":")
        if len(split) == 2:
            host, port = split
            port = int(port)
        else:
            host, port = split[0], None
        if path:
            pathSegments = path.split(u"/")
            if not pathSegments[0]:
                pathSegments.pop(0)
                rooted = True
            else:
                rooted = False
        else:
            pathSegments = []
            rooted = bool(netloc)
        if query:
            queryParameters = [(qe.split(u"=", 1)
                                if u'=' in qe else (qe, None))
                               for qe in query.split(u"&")]
        else:
            queryParameters = []
        return cls(scheme, host, pathSegments, queryParameters, fragment, port,
                   rooted)


    def child(self, segment):
        """
        Construct a L{URL} where the given path segment is a child of this url,
        presering the query and fragment.

        For example::

            >>> URL.fromText(u"http://localhost/a/b?x=y").child(u"c").asText()
            u'http://localhost/a/b/c?x=y'

        @param segment: A path segment.
        @type segment: L{unicode}

        @return: a new L{URL} with the additional path segment.
        @rtype: L{URL}
        """
        if not isinstance(segment, unicode):
            raise TypeError("Given path must be unicode.")
        l = list(self.pathSegments)
        if l[-1] == u'':
            l[-1] = segment
        else:
            l.append(segment)
        return self.replace(pathSegments=l)


    def sibling(self, segment):
        """
        Construct a url where the given path segment is a sibling of this url.

        @param segment: A path segment.
        @type segment: L{unicode}

        @return: a new L{URL} with its final path segment replaced with
            C{segment}.
        @rtype: L{URL}
        """
        if not isinstance(segment, unicode):
            raise TypeError("Given path must be unicode.")
        l = list(self.pathSegments)
        l[-1] = segment
        return self.replace(pathSegments=l)


    def click(self, href):
        """
        Resolve the given URI reference relative to this (base) URI.

        The resulting URI should match what a web browser would generate if you
        click on C{href} in the context of this URI.

        @param href: a URI reference
        @type href: L{unicode} or ASCII L{str}

        @return: a new absolute L{URL}

        @see: RFC 3986 section 5, Reference Resolution
        """
        if not len(href):
            return self

        clicked = URL.fromText(href)

        queryParameters = clicked.queryParameters
        if clicked.absolute:
            return clicked
        elif clicked.scheme and not clicked.rooted:
            # Schemes with relative paths are not well-defined.  RFC 3986 calls
            # them a "loophole in prior specifications" that should be avoided,
            # or supported only for backwards compatibility.
            raise NotImplementedError(
                'absolute URI with rootless path: %r' % (href,)
            )
        else:
            if clicked.rooted:
                pathSegments = clicked.pathSegments
            elif clicked.pathSegments:
                pathSegments = self.pathSegments[:-1] + clicked.pathSegments
            else:
                pathSegments = self.pathSegments
                if not queryParameters:
                    queryParameters = self.queryParameters
        return self.replace(
            scheme=clicked.scheme or self.scheme,
            host=clicked.host or self.host,
            port=clicked.port or self.port,
            pathSegments=_resolveDotSegments(pathSegments),
            queryParameters=queryParameters,
            fragment=clicked.fragment
        )


    def asURI(self):
        """
        Apply percent-encoding rules to convert this L{URL} into a URI.

        @return: a new L{URL} with its path-segments, query-parameters, and
            hostname appropriately decoded, so that they are all in the
            US-ASCII range.
        @rtype: L{URL}
        """
        return self.replace(
            host=self.host.encode("idna").decode("ascii"),
            pathSegments=(_maximalPercentEncode(segment, _validInPath)
                          for segment in self.pathSegments),
            queryParameters=(
                tuple(_maximalPercentEncode(x, _validInQuery)
                      if x is not None else None
                      for x in (k, v))
                for k, v in self.queryParameters
            ),
            fragment=_maximalPercentEncode(self.fragment, _validInFragment)
        )


    def asIRI(self):
        """
        Apply percent-decoding rules to convert this L{URL} into an IRI.

        @return: a new L{URL} with its path-segments, query-parameters, and
            hostname appropriately decoded.
        @rtype: L{URL}
        """
        return self.replace(
            host=self.host.decode("idna"),
            pathSegments=[_percentDecode(segment)
                          for segment in self.pathSegments],
            queryParameters=[
                tuple(_percentDecode(x)
                      if x is not None else None
                      for x in (k, v))
                for k, v in self.queryParameters
            ],
            fragment=_percentDecode(self.fragment)
        )


    def asText(self):
        """
        Convert this URL to its canonical textual representation.

        @return: The serialized textual representation of this L{URL}, such as
            C{u"http://example.com/some/path?some=query"}.
        @rtype: L{unicode}
        """
        path = u'/'.join([u''] + [_minimalPercentEncode(segment, _validInPath)
                                  for segment in self.pathSegments])
        query = '&'.join(
            u'='.join(
                (_minimalPercentEncode(x, _validInQuery)
             for x in ([k] if v is None
                       else [k, v]))
            )
            for (k, v) in self.queryParameters
        )
        if self.port == _schemeDefaultPorts.get(self.scheme):
            authority = self.host
        else:
            authority = u"{host}:{port}".format(host=self.host,
                                                port=self.port)
        return urlunsplit((self.scheme, authority, path, query, self.fragment))


    def __repr__(self):
        """
        Convert this URL to an C{eval}-able representation that shows all of
        its constituent parts.
        """
        return ('URL.fromText({})').format(repr(self.asText()))
