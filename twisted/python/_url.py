# -*- test-case-name: twisted.python.test.test_url -*-
# -*- coding: utf-8 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
URL parsing, construction and rendering.
"""

try:
    from urlparse import urlsplit, urlunsplit
    from urllib import quote as urlquote, unquote as urlunquote
except ImportError:
    from urllib.parse import (urlsplit, urlunsplit,
                              quote as urlquote,
                              unquote_to_bytes as urlunquote)

from collections import Sequence
from unicodedata import normalize

# Zero dependencies within Twisted: this module should probably be spun out
# into its own library fairly soon.

unicode = type(u'')

# RFC 3986 section 2.2, Reserved Characters
_genDelims = u':/?#[]@'
_subDelims = u"!$&'()*+,;="

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



def _querify(args, kw):
    """
    Convert the given args and kwargs into a query fragment.  For an
    explanation of the rules this uses to convert between argument signatures
    and query parameters, see L{URL.add}.

    @param args: a tuple of positional arguments

    @param kw: a dictionary of keyword arguments

    @return: an n-tuple of 2-tuples of unicode (key, value) query parameters
        represented by the given args and kwargs.
    """
    def _primitive(p):
        if isinstance(p, unicode):
            return p
        elif isinstance(p, (float, int)):
            return unicode(p)
    def _subnormalize(q):
        for k, v in q:
            if v is None or isinstance(v, unicode):
                yield unicode(k), v
            elif isinstance(v, Sequence):
                for vv in v:
                    yield unicode(k), _primitive(vv)
            else:
                yield unicode(k), _primitive(v)

    def _normalize(q):
        return tuple(_subnormalize(q))
    def _querifyDict(d):
        return _normalize(sorted(d.items()))
    if len(args) == 2:
        name, value = args
        return _normalize([(name, value)])
    elif len(args) == 1:
        if isinstance(args[0], unicode):
            return _normalize([(args[0], None)])
        elif isinstance(args[0], dict):
            return _querifyDict(args[0])
    elif len(args) == 0:
        return _querifyDict(kw)
    # else:
    #     raise TypeError()



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
    quoted = urlquote(
        normalize("NFC", text).encode("utf-8"), (safe + u'%').encode("ascii")
    )
    if not isinstance(quoted, unicode):
        quoted = quoted.decode("ascii")
    return quoted



def _percentDecode(text):
    """
    Replace percent-encoded characters with their UTF-8 equivalents.

    @param text: The text with percent-encoded UTF-8 in it.
    @type text: L{unicode}

    @return: the encoded version of C{text}
    @rtype: L{unicode}
    """
    try:
        quotedBytes = text.encode("ascii")
    except UnicodeEncodeError:
        return text
    unquotedBytes = urlunquote(quotedBytes)
    try:
        return unquotedBytes.decode("utf-8")
    except UnicodeDecodeError:
        return text



def _resolveDotSegments(path):
    """
    Normalise the URL path by resolving segments of '.' and '..'.

    @param path: list of path segments

    @see: RFC 3986 section 5.2.4, Remove Dot Segments

    @return: a new L{list} of path segments with the '.' and '..' elements
        removed and resolved.
    """
    segs = []

    for seg in path:
        if seg == u'.':
            pass
        elif seg == u'..':
            if segs:
                segs.pop()
        else:
            segs.append(seg)

    if list(path[-1:]) in ([u'.'], [u'..']):
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

    You can construct L{URL} objects by passing in these components directly,
    like so::

        >>> from twisted.python.url import URL
        >>> URL(scheme=u'https', host=u'example.com',
        ...     path=[u'hello', u'world'])
        URL.fromText(u'https://example.com/hello/world')

    Or you can use the L{fromText} method you can see in the output there::

        >>> URL.fromText(u'https://example.com/hello/world')
        URL.fromText(u'https://example.com/hello/world')

    There are two major advantages of using L{URL} over representing URLs as
    strings.  The first is that it's really easy to evaluate a relative
    hyperlink, for example, when crawling documents, to figure out what is
    linked::

        >>> URL.fromText(u'https://example.com/base/uri/').click("/absolute")
        URL.fromText(u'https://example.com/absolute')
        >>> (URL.fromText(u'https://example.com/base/uri/')
        ...  .click("relative/path"))
        URL.fromText(u'https://example.com/base/uri/relative/path')

    The other is that URLs have two normalizations.  One representation is
    suitable for humans to read, because it can represent data from many
    character sets - this is the Internationalized, or IRI, normalization.  The
    other is the older, US-ASCII-only representation, which is necessary for
    most contexts where you would need to put a URI.  You can convert *between*
    these representations according to certain rules.  L{URL} exposes these
    conversions as methods::

        >>> URL.fromText(u"https://→example.com/foo⇧bar/").asURI()
        URL.fromText(u'https://xn--example-dk9c.com/foo%E2%87%A7bar/')
        >>> (URL.fromText(u'https://xn--example-dk9c.com/foo%E2%87%A7bar/')
             .asIRI())
        URL.fromText(u'https://\u2192example.com/foo\u21e7bar/')

    @see: U{RFC 3986, Uniform Resource Identifier (URI): Generic Syntax
        <https://tools.ietf.org/html/rfc3986>}
    @see: U{RFC 3987, Internationalized Resource Identifiers
        <https://tools.ietf.org/html/rfc3987>}

    @ivar scheme: The URI scheme.
    @type scheme: L{unicode}

    @ivar host: The host name.
    @type host: L{unicode}

    @ivar port: The port number.
    @type port: L{int}

    @ivar path: The path segments.
    @type path: L{tuple} of L{unicode}.

    @ivar query: The query parameters, as (name, value) pairs.
    @type query: L{tuple} of 2-L{tuple}s of (name: L{unicode}, value:
        (L{unicode} for values or C{None} for stand-alone query parameters with
        no C{=} in them)).

    @ivar fragment: The fragment identifier.
    @type fragment: L{unicode}

    @ivar rooted: Does the path start with a C{/}?  This is taken from the
        terminology in the BNF grammar, specifically the C{path-rootless},
        rule, since "absolute path" and "absolute URI" are somewhat ambiguous.
        C{path} does not contain the implicit prefixed C{"/"} since that is
        somewhat awkward to work with.
    @type rooted: L{bool}
    """

    def __init__(self, scheme=None, host=None, path=None,
                 query=None, fragment=None, port=None,
                 rooted=None):
        """
        Create a new L{URL} from structured information about itself.

        @ivar scheme: The URI scheme.
        @type scheme: L{unicode}

        @ivar host: The host portion of the netloc.
        @type host: L{unicode}

        @ivar port: The port number portion of the netloc.
        @type port: L{int}

        @ivar path: The path segments.
        @type path: Iterable of L{unicode}.

        @ivar query: The query parameters, as name-value pairs
        @type query: Iterable of pairs of L{unicode} (or C{None}, for values).

        @ivar fragment: The fragment identifier.
        @type fragment: L{unicode}

        @ivar rooted: Does the path start with a C{/}?  This is taken from the
            terminology in the BNF grammar, specifically the C{path-rootless},
            rule, since "absolute path" and "absolute URI" are somewhat
            ambiguous.  C{path} does not contain the implicit prefixed C{"/"}
            since that is somewhat awkward to work with.
        @type rooted: L{bool}
        """
        # Fall back to defaults.
        if path is None:
            path = []
        if query is None:
            query = []
        if fragment is None:
            fragment = u''
        if host is not None and scheme is None:
            scheme = u'http'
        if port is None:
            port = _schemeDefaultPorts.get(scheme)
        if host and query and not path:
            path = [u'']

        # Set attributes.
        self._scheme = _checkUnicodeOrNone(scheme) or u''
        self._host = _checkUnicodeOrNone(host) or u''
        self._path = tuple(map(_checkUnicodeOrNone, path))
        self._query = tuple((_checkUnicodeOrNone(k),
                             _checkUnicodeOrNone(v)) for (k, v) in
                            query)
        self._fragment = _checkUnicodeOrNone(fragment)
        self._port = port
        if rooted is None:
            rooted = bool(host)
        self._rooted = rooted

    scheme = property(lambda self: self._scheme)
    host = property(lambda self: self._host)
    port = property(lambda self: self._port)
    path = property(lambda self: self._path)
    query = property(lambda self: self._query)
    fragment = property(lambda self: self._fragment)
    rooted = property(lambda self: self._rooted)

    @property
    def authority(self):
        """
        The authority (network location) portion of the URL.
        """
        if self.port == _schemeDefaultPorts.get(self.scheme):
            return self.host
        else:
            return u"{host}:{port}".format(host=self.host,
                                           port=self.port)


    def __eq__(self, other):
        """
        L{URL}s are equal to L{URL} objects whose attributes are equal.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        for attr in ['scheme', 'host', 'path', 'query',
                     'fragment', 'port', 'rooted']:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True


    def __ne__(self, other):
        """
        L{URL}s are unequal to L{URL} objects whose attributes are unequal.
        """
        if not isinstance(other, self.__class__):
            return NotImplemented
        return not self.__eq__(other)


    @property
    def absolute(self):
        """
        Is this URL complete enough to resolve a resource without resolution
        relative to a base-URI?
        """
        return bool(self.scheme and self.host)


    def replace(self, scheme=_unspecified, host=_unspecified,
                path=_unspecified, query=_unspecified,
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

        @param path: the path segments of the new URL; if unspecified,
            the path segments of this URL.
        @type path: iterable of L{unicode}

        @param query: the query elements of the new URL; if
            unspecified, the query segments of this URL.
        @type query: iterable of 2-L{tuple}s of key, value.

        @param fragment: the fragment of the new URL; if unspecified, the query
            segments of this URL.
        @type fragment: L{unicode}

        @param port: the port of the new URL; if unspecified, the port of this
            URL.
        @type port: L{int}

        @param rooted: C{True} if the given C{path} are meant to start
            at the root of the host; C{False} otherwise.  Only meaningful for
            relative URIs.
        @type rooted: L{bool}

        @return: a new L{URL}.
        """
        return self.__class__(
            scheme=_optional(scheme, self.scheme),
            host=_optional(host, self.host),
            path=_optional(path, self.path),
            query=_optional(query, self.query),
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
        (scheme, netloc, path, query, fragment) = (
            (u'' if x == b'' else x) for x in urlsplit(s)
        )
        split = netloc.split(u":")
        if len(split) == 2:
            host, port = split
            port = int(port)
        else:
            host, port = split[0], None
        if path:
            path = path.split(u"/")
            if not path[0]:
                path.pop(0)
                rooted = True
            else:
                rooted = False
        else:
            path = ()
            rooted = bool(netloc)
        if query:
            query = ((qe.split(u"=", 1) if u'=' in qe else (qe, None))
                     for qe in query.split(u"&"))
        else:
            query = ()
        return cls(scheme, host, path, query, fragment, port, rooted)


    def child(self, *segments):
        """
        Construct a L{URL} where the given path segments are a child of this
        url, presering the query and fragment.

        For example::

            >>> (URL.fromText(u"http://localhost/a/b?x=y")
                 .child(u"c", u"d").asText())
            u'http://localhost/a/b/c?x=y'

        @param segments: A path segment.
        @type segments: L{tuple} of L{unicode}

        @return: a new L{URL} with the additional path segments.
        @rtype: L{URL}
        """
        for segment in segments:
            if not isinstance(segment, unicode):
                raise TypeError("Given path must be unicode.")
        return self.replace(
            path=self.path[:-1 if (self.path and self.path[-1] == u'')
                           else None] + segments
        )


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
        return self.replace(path=self.path[:-1] + (segment,))


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

        query = clicked.query
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
                path = clicked.path
            elif clicked.path:
                path = self.path[:-1] + clicked.path
            else:
                path = self.path
                if not query:
                    query = self.query
        return self.replace(
            scheme=clicked.scheme or self.scheme,
            host=clicked.host or self.host,
            port=clicked.port or self.port,
            path=_resolveDotSegments(path),
            query=query,
            fragment=clicked.fragment
        )


    def asURI(self):
        """
        Convert a L{URL} object that potentially contains non-ASCII characters
        into a L{URL} object where all non-ASCII text has been encoded
        appropriately.  This is useful to do in preparation for sending a
        L{URL}, or portions of it, over a wire protocol.  For example::

            >>> URL.fromText(u"https://→example.com/foo⇧bar/").asURI()
            URL.fromText(u'https://xn--example-dk9c.com/foo%E2%87%A7bar/')

        @return: a new L{URL} with its path-segments, query-parameters, and
            hostname appropriately decoded, so that they are all in the
            US-ASCII range.
        @rtype: L{URL}
        """
        return self.replace(
            host=self.host.encode("idna").decode("ascii"),
            path=(_maximalPercentEncode(segment, _validInPath)
                  for segment in self.path),
            query=(
                tuple(_maximalPercentEncode(x, _validInQuery)
                      if x is not None else None
                      for x in (k, v))
                for k, v in self.query
            ),
            fragment=_maximalPercentEncode(self.fragment, _validInFragment)
        )


    def asIRI(self):
        """
        Convert a L{URL} object that potentially contains text that has been
        percent-encoded or IDNA encoded into a L{URL} object containing the
        text as it should be presented to a human for reading.

        For example::

            >>> (URL.fromText(u'https://xn--example-dk9c.com/foo%E2%87%A7bar/')
                 .asIRI())
            URL.fromText(u'https://\u2192example.com/foo\u21e7bar/')

        @return: a new L{URL} with its path-segments, query-parameters, and
            hostname appropriately decoded.
        @rtype: L{URL}
        """
        try:
            asciiHost = self.host.encode("ascii")
        except UnicodeEncodeError:
            textHost = self.host
        else:
            textHost = asciiHost.decode("idna")
        return self.replace(
            host=textHost,
            path=[_percentDecode(segment) for segment in self.path],
            query=[
                tuple(_percentDecode(x)
                      if x is not None else None
                      for x in (k, v))
                for k, v in self.query
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
                                  for segment in self.path])
        query = '&'.join(
            u'='.join((_minimalPercentEncode(x, _validInQuery)
                       for x in ([k] if v is None else [k, v])))
            for (k, v) in self.query
        )
        return urlunsplit((self.scheme, self.authority, path, query,
                           self.fragment))


    def __repr__(self):
        """
        Convert this URL to an C{eval}-able representation that shows all of
        its constituent parts.
        """
        return ('URL.fromText({})').format(repr(self.asText()))


    def add(self, *args, **kw):
        """
        Add a query argument with the given value None indicates that the
        argument has no value.
        """
        return self.replace(
            query=self.query + _querify(args, kw)
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
        q = [(k, v) for (k, v) in self.query if k != name]
        idx = next((i for (i, (k, v)) in enumerate(self.query)
                    if k == name), -1)
        q[idx:idx] = [(name, value)]
        return self.replace(query=q)


    def get(self, name):
        """
        Retrieve a list of values for the given named query parameter.

        @param name: The name of the query parameter to retrieve.

        @return: all the values associated with the key; for example, for the
            query string C{u"x=1&x=2"}, C{url.query.get(u"x")} would return
            C{[u'1', u'2']}; C{url.query.get(u"y")} (since there is no C{"y"}
            parameter) would return the empty list, C{[]}.
        @rtype: L{list} of L{unicode}
        """
        return [value for (key, value) in self.query
                if name == key]


    def remove(self, name):
        """
        Remove all query arguments with the given name.

        @param name: The name of the query parameter to remove.

        @return: a new L{URL} with the parameter removed.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        return self.replace(filter(lambda x: x[0] != name,
                                   self.query))
