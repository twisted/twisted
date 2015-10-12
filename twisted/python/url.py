# -*- test-case-name: twisted.python.test.test_url -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
URL parsing, construction and rendering.

Valid parsable URLs may show up looking like
C{b'http://example.com/foo%2Fbar/baz'}.  Or they might show up as the
ASCII-decoded equivalent: C{u'http://example.com/foo%2Fbar/baz'}.  The fully
decoded human-readable version, however, is not something the URL code should
be parsing; it should only ever be displayed, not used a reference or key.  For
example, in this case it would be the problematic
C{u'http://example.com/foo/bar/baz'}, assuming a UTF-8 encoding for '%2F'.  As
this example shows, the only reasonable thing to parse is still-encoded URLs.
L{unicode} URLs with non-ASCII bytes can also be ignored as invalid.

The Unicode encoding of the %-encoded characters (e.g. the '%2F' above) is
another issue.  Domains will always use IDNA.  Paths will usually (but probably
not always) be UTF-8, query strings can be whatever the hell the browser feels
like, either UTF-8 or the encoding of the page.  The path and query string may
well have different encodings, and the encodings for path and query string may
not be known!  This module will therefore allow the original bytes in paths and
queries to be preserved, so they can be passed through to someone who hopefully
does know how to decode them.

Of course, if there's no % in the path or query, you can just assume an
encoding of ASCII.

@see: U{RFC 3986, Uniform Resource Identifier (URI): Generic Syntax
    <https://tools.ietf.org/html/rfc3986>}
@see: U{RFC 3987, Internationalized Resource Identifiers
    <https://tools.ietf.org/html/rfc3986>}
"""

from urlparse import urlsplit, urlunsplit
from urllib import quote as urlquote
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



def _resolveDotSegments(pathSegments):
    """
    Normalise the URL path by resolving segments of '.' and '..'.

    @param pathSegments: list of path segments

    @see: RFC 3986 section 5.2.4, Remove Dot Segments
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

    if pathSegments[-1:] in ([u'.'],[u'..']):
        segs.append(u'')

    return segs



def _checkUnicodeOrNone(s):
    """
    Raise C{TypeError} if C{s} is C{None} or an instance of L{unicode}.
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
        """
        _checkUnicodeOrNone(name)
        _checkUnicodeOrNone(value)

        return self._url.replace(queryParameters=self._url.queryParameters +
                            [(name, value)])


    def set(self, name, value=None):
        """
        Remove all existing occurrences of the query argument 'name', *if it
        exists*, then add the argument with the given value.

        C{None} indicates that the argument has no value.
        """
        if (not isinstance(name, unicode) or
            not isinstance(value, (unicode, None.__class__))):
            raise TypeError("name and value must be unicode.")
        ql = self._url.queryParameters[:]
        # Preserve the original position of the query key in the list
        i = 0
        for (k, v) in ql:
            if k == name:
                break
            i += 1
        q = filter(lambda x: x[0] != name, ql)
        q.insert(i, (name, value))
        return self._url.replace(queryParameters=q)


    def get(self, name):
        """
        Retrieve a list of values for the given named query parameter.

        @return: all the values associated with the key; for example, for the
            query string x=1&x=2, C{[u'1', u'2']}
        @rtype: L{list} of L{unicode}
        """
        return [value for (key, value) in self._url.queryParameters
                if name == key]


    def remove(self, name):
        """
        Remove all query arguments with the given name.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        return self._url.replace(filter(lambda x: x[0] != name,
                                   self._url.queryParameters))


    def clear(self):
        """
        Remove all existing query arguments.
        """
        return self._url.replace(queryParameters=[])






class URL(object):
    """
    Represents a URL and provides a convenient API for modifying its parts.

    A URL is split into a number of distinct parts: scheme, netloc (domain
    name), path segments, query parameters and fragment identifier.

    Methods are provided to modify many of the parts of the URL, especially the
    path and query parameters.  Values can be passed to methods as-is; encoding
    and escaping is handled automatically.

    There preferred way of creating a URL is to call L{URL.fromText}, a class
    method that parses the text format of URLs.

    URL subclasses with different constructor signatures should override
    L{replace} to ensure that the numerous instance methods which return copies
    do so correctly.  Additionally, the L{fromText} method will need to be
    overridden.

    The following attributes are always stored and passed to C{__init__} in
    decoded form (that is, as L{unicode}, without any percent-encoding).
    C{str} objects should never be passed to C{__init__}!

    @ivar scheme: the URI scheme
    @type scheme: L{unicode}

    @ivar host: the host portion of the netloc.
    @type host: L{unicode}

    @ivar port: The port number portion of the netloc.
    @type port: L{int}

    @ivar pathSegments: the path segments
    @type pathSegments: list of L{unicode}

    @ivar queryParameters: the query parameters, as name-value pairs
    @type queryParameters: list of pairs of L{unicode} (or C{None}, for values)

    @ivar fragment: the fragment identifier
    @type fragment: L{unicode}

    @ivar rooted: Does the path start with a C{/}?  This is taken from the
        terminology in the BNF grammar, specifically the C{path-rootless},
        rule, since "absolute path" and "absolute URI" are somewhat ambiguous.
        C{pathSegments} does not contain the implicit prefixed C{"/"} since
        that is somewhat awkward to work with.
    @type rooted: L{bool}
    """

    compareAttributes = ['scheme', 'host', 'pathSegments',
                         'queryParameters', 'fragment', 'port']

    def __init__(self, scheme=None, host=None, pathSegments=None,
                 queryParameters=None, fragment=None, port=None,
                 rooted=True):
        # Defaults.
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
        self.scheme = _checkUnicodeOrNone(scheme)
        self.host = _checkUnicodeOrNone(host)
        self.pathSegments = map(_checkUnicodeOrNone, pathSegments)
        self.queryParameters = [(_checkUnicodeOrNone(k),
                                 _checkUnicodeOrNone(v)) for (k, v) in
                                queryParameters]
        self.fragment = _checkUnicodeOrNone(fragment)
        self.port = port
        self.rooted = rooted


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        for attr in ['scheme', 'host', 'pathSegments', 'queryParameters',
                     'fragment', 'port', 'rooted']:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True


    def __ne__(self, other):
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

        @param host: the host of the new URL; if unspecified, the host of this
            URL.

        @param pathSegments: the path segments of the new URL; if unspecified,
            the path segments of this URL.

        @param queryParameters: the query elements of the new URL; if
            unspecified, the query segments of this URL.

        @param fragment: the fragment of the new URL; if unspecified, the query
            segments of this URL.

        @param port: the port of the new URL; if unspecified, the port of this
            URL.
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

    # Path manipulations:


    def sibling(self, path):
        """
        Construct a url where the given path segment is a sibling of this url.
        """
        if not isinstance(path, unicode):
            raise TypeError("Given path must be unicode.")
        l = self.pathSegments[:]
        l[-1] = path
        return self.replace(pathSegments=l)


    def child(self, path):
        """
        Construct a url where the given path segment is a child of this url.
        """
        if not isinstance(path, unicode):
            raise TypeError("Given path must be unicode.")
        l = self.pathSegments[:]
        if l[-1] == u'':
            l[-1] = path
        else:
            l.append(path)
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
            # schemes with relative paths are not well-defined.  RFC 3986
            # calls them a "loophole in prior specifications" that should
            # be avoided, or supported only for backwards compatibility.
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
        """
        return self.replace(
            host=self.host.encode("idna").decode("ascii"),
            pathSegments=[_maximalPercentEncode(segment, _validInPath)
                          for segment in self.pathSegments],
            queryParameters=[
                tuple(_maximalPercentEncode(x, _validInQuery)
                      if x is not None else None
                      for x in (k, v))
                for k, v in self.queryParameters
            ],
            fragment=_maximalPercentEncode(self.fragment, _validInFragment)
        )


    def asIRI(self):
        """
        Apply percent-decoding rules to convert this L{URL} into an IRI.
        """
        return self.replace()


    def asText(self):
        """
        Convert this URL to its textual representation.
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
        return (
            '%s(scheme=%r, host=%r, pathSegments=%r, queryParameters=%r, '
            'fragment=%r, port=%r)'
            % (type(self).__name__,
               self.scheme,
               self.host,
               self.pathSegments,
               self.queryParameters,
               self.fragment,
               self.port))
