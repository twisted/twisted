# -*- test-case-name: twisted.python.test.test_url -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
URL parsing, construction and rendering.

Valid parsable URLs may show up looking like
C{'http://example.com/foo%2Fbar/baz'}.  Or they might show up as the
ASCII-decoded equivalent: C{u'http://example.com/foo%2Fbar/baz'}.  The fully
decoded human-readable version, however, is not something the URL code should
be parsing; it should only ever be displayed, not used a reference or key.  For
example, in this case it would be the problematic
C{u'http://example.com/foo/bar/baz'}, assuming a UTF-8 encoding for '%2F'.  As
this example shows, the only reasonable thing to parse is still-encoded URLs.
C{str} URLs with non-ASCII bytes can also be ignored as invalid.

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

"""
XXX temporary design notes and TODOs XXX

    - parseIRI() should only accept either C{str}, or C{unicode} that will then
      immediately be encoded in ASCII.  If the encoding fails the URL will be
      rejected; it may be human readable, but we cannot guarantee parsing it
      correctly.  It may be that this a human-readable version that has already
      been decoded, with lost information as a result (e.g.
      C{u'http://example.com/foo/bar/baz'}) above, and we will parse it
      incorrectly.  There is nothing we can do about that however, it's up to
      the user not to feed as bad data.  The various other utility functions
      used for parsing can thereafter be modified to assume only C{str} as
      input.

    - URL objects should somehow preserve the incoming path and query, and deal
      with the potential for different or unknown encodings somehow.  API
      details are not yet clear; exarkun suggests Segment() objects that have
      original bytes and optional decoded version, and presumably we could have
      equivalent QueryArgument for query.  It should be possible to reencode a
      URL and get back the same bytes as what was originally parsed.

    - The change where URL is all unicode and only accepts Unicode methods may
      therefore be wrong...  or maybe you shouldn't be modifying the path/query
      if you don't know the encoding.
"""

import urlparse
import urllib

# RFC 3986 section 2.2, Reserved Characters
_genDelims = ':/?#[]@'
_subDelims = "!$&'()*+,;="


class IRIDecodeError(ValueError):
    """
    Failed to decode string as an IRI component.

    If the original URI contains non-ASCII percent-encoded octets not from
    UTF-8, those octets should be separately decoded to L{unicode} first.
    """



def iriencode(s, unencoded=''):
    """
    Encode the given URI/IRI component to RFC 3987 percent-encoded form.

    Characters in the unreserved set (see RFC 3986 section 2, Characters) appear
    in the result without percent-encoding.  Particular components (for example,
    path segments) may define additional characters that do not need
    percent-encoding:  these can be specified with the C{unencoded} parameter.

    @param s: string to encode
    @type s: L{unicode} (or ASCII L{str})

    @param unencoded: additional characters to exempt from percent-encoding
    @type unencoded: L{str}

    @rtype: ASCII L{str}

    @raise UnicodeDecodeError: C{s} is a non-ASCII L{str}
    @raise TypeError: C{s} is not a string
    """
    if isinstance(s, str):
        s = s.decode('ascii')
    if isinstance(s, unicode):
        return urllib.quote(s.encode('utf-8'), safe='-._~'+unencoded)
    else:
        raise TypeError(s)



def iriencodePath(s):
    """
    L{iriencode} convenience wrapper for path segments.

    This avoids percent-encoding characters in L{_subDelims} and C{':@'}.

    @see: RFC 3986 section 3.3, Path

    @param s: an un-encoded path segment.

    @return: a percent-encoded path segment.
    """
    return iriencode(s, unencoded=_subDelims + ':@')



_queryfieldSafe = ((_subDelims + ':@/?')
                   .replace('&', '')
                   .replace('=', '')
                   .replace('+', ''))

def iriencodeQuery(s):
    """
    L{iriencode} convenience wrapper for x-www-form-urlencoded query fields.

    This is like L{iriencodeFragment}, but without C{'&=+'}.

    @param s: an un-encoded value for use as a query string.

    @return: a percent-encoded query string.
    """
    return iriencode(s, unencoded=_queryfieldSafe)



def iriencodeFragment(s):
    """
    L{iriencode} convenience wrapper for fragment components.

    This is like L{iriencodePath}, but with the addition of C{'/?'}.

    @see: RFC 3986 section 3.5, Fragment

    @param s: an un-encoded value for use as a fragment.

    @return: a percent-encoded IRI fragment.
    """
    return iriencode(s, unencoded=_subDelims + ':@/?')



def iridecode(s):
    """
    Decode the given URI/IRI component from RFC 3987 percent-encoded form.

    @param s: string to decode
    @type s: ASCII L{str} or L{unicode}

    @rtype: L{unicode}

    @raise IRIDecodeError: C{s} contained invalid percent-encoded octets
    @raise UnicodeDecodeError: C{s} is a non-ASCII L{str}
    @raise TypeError: C{s} is not a string
    """

    # Note: urllib.unquote interprets percent-encoded octets in unicode strings
    # as Unicode codepoints (effectively decoding them as Latin1), so we cannot
    # pass it unicode strings directly.

    # It doesn't change non-percent-encoded octets in strings, though, so we
    # can encode unicode strings to UTF-8 first: decoding the result from UTF-8
    # then restores the original Unicode characters in addition to the ones
    # that were percent-encoded.

    if isinstance(s, str):
        s = s.decode('ascii')
    if isinstance(s, unicode):
        try:
            return urllib.unquote(s.encode('utf-8')).decode('utf-8')
        except UnicodeDecodeError:
            raise IRIDecodeError(s)
    else:
        raise TypeError(s)



def _querify(fields):
    """
    Join key/value fields into an x-www-form-urlencoded string.

    No character encoding occurs.

    @param fields: list of key (L{str}) / value (L{str} or C{None}) pairs

    @return: x-www-form-urlencoded L{str}
    """
    for (k, v) in fields:
        if v is not None:
            yield '='.join((k, v))
        elif k:
            yield k
querify = lambda fields: '&'.join(_querify(fields))



def _unquerify(query):
    """
    Split an x-www-form-urlencoded string into key/value fields.

    C{'+'} is replaced with C{' '}, but no other character decoding occurs.

    @param query: x-www-form-urlencoded L{str}

    @return: list of key (L{str}) / value (L{str} or C{None}) pairs
    """
    query = query.replace('+', ' ')
    for x in query.split('&'):
        if '=' in x:
            yield tuple(x.split('=', 1))
        elif x:
            yield (x, None)
unquerify = lambda query: list(_unquerify(query))



def _maybe(f, x):
    """
    Call C{f} on C{x} if C{x} is not None.

    @param f: a 1-argument callable taking C{x} and returning something

    @param x: a value (or C{None})

    @return: C{f(x)} or C{None}.
    """
    if x is not None:
        return f(x)



def parseIRI(s):
    """
    Parse a URI/IRI into its components.

    The URI is split into five major components: I{scheme}, I{netloc}, I{path},
    I{query}, and I{fragment}.

    The I{path} and I{query} components are further parsed:

        - I{path} is split into a list of segments, such that a path containing
          I{N} C{'/'} separators will always have I{N+1} segments.  A leading
          segment of C{u''} indicates an absolute path reference; otherwise,
          the path is relative (this implies that I{netloc} is absent).

        - I{query} is split into a list of key and (optional) value fields.
          (see L{unquerify})

    All returned components are fully percent-decoded to L{unicode} strings.

    @param s: a string containing a URI
    @type s: either L{unicode} or L{bytes}

    @return: C{(scheme, netloc, pathsegs, querysegs, fragment)}, per above
    @rtype: the same type as C{s}
    """
    (scheme, netloc, path, query, fragment) = urlparse.urlsplit(s)
    pathsegs = map(iridecode, path.split('/'))
    querysegs = [(iridecode(k), _maybe(iridecode, v))
                 for (k, v) in unquerify(query)]
    if isinstance(netloc, str):
        netloc = netloc.decode("idna")
    elif isinstance(netloc, unicode):
        try:
            netloc = netloc.decode("idna")
        except UnicodeError:
            pass
    return (iridecode(scheme),
            netloc,
            pathsegs,
            querysegs,
            iridecode(fragment))



def unparseIRI((scheme, netloc, pathsegs, querysegs, fragment)):
    """
    Format a URI/IRI from its components.

    See L{parseIRI}; this is the inverse.

    @param scheme: A URI scheme.  (like C{http} or C{https})

    @param netloc: A URI network location (like C{example.com})

    @param pathsegs: a list of path segments

    @param querysegs: a list of key, value pairs for encoding in the query.

    @param fragment: the fragment (the portion of the URI after C{#})

    @return: An IRI string.
    """
    path = '/'.join(map(iriencodePath, pathsegs))
    query = querify((iriencodeQuery(k), _maybe(iriencodeQuery, v))
                    for (k, v) in querysegs)
    return urlparse.urlunsplit(
        (iriencode(scheme),
         netloc.encode("idna"),
         path,
         query,
         iriencodeFragment(fragment)))


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



class URL(object):
    """
    Represents a URL (actually, an IRI) and provides a convenient API for
    modifying its parts.

    A URL is split into a number of distinct parts: scheme, netloc (domain
    name), path segments, query parameters and fragment identifier.

    Methods are provided to modify many of the parts of the URL, especially the
    path and query parameters.  Values can be passed to methods as-is; encoding
    and escaping is handled automatically.

    There preferred way of creating a URL is to call fromString, a class method
    that parses the string format of URLs.

    URL subclasses with different constructor signatures should override
    L{replace} to ensure that the numerous instance methods which return copies
    do so correctly.  Additionally, the L{fromString} method will need to be
    overridden.

    The following attributes are always stored and passed to __init__ in
    decoded form (that is, as C{unicode}, without any percent-encoding).
    C{str} objects should never be passed to C{__init__}!

    @ivar scheme: the URI scheme
    @type scheme: C{unicode}

    @ivar hostname: the host (and possibly port)
    @type hostname: C{unicode}

    @ivar pathsegs: the path segments
    @type pathsegs: list of C{unicode}

    @ivar querysegs: the query parameters, as name-value pairs
    @type querysegs: list of pairs of C{unicode} (or C{None}, for values)

    @ivar fragment: the fragment identifier
    @type fragment: C{unicode}
    """

    def __init__(self, scheme=u'http', hostname=u'', pathsegs=None,
                 querysegs=None, fragment=None, port=None):
        def _unicodify(s):
            if not isinstance(s, (unicode, None.__class__)):
                raise TypeError("%r is not unicode" % (s,))
            return s
        self.scheme = _unicodify(scheme)
        self.hostname = _unicodify(hostname)
        if pathsegs is None:
            pathsegs = [u'']
        self.pathsegs = map(_unicodify, pathsegs)
        if querysegs is None:
            querysegs = []
        self.querysegs = [(_unicodify(k), _unicodify(v))
                           for (k, v) in querysegs]
        if fragment is None:
            fragment = u''
        self.fragment = _unicodify(fragment)
        if port is None:
            port = _schemeDefaultPorts.get(scheme)
        self.port = port


    @property
    def path(self):
        """
        The percent-encoded path component of this URL.

        @type: L{str}
        """
        return '/'.join(map(iriencodePath, self.pathsegs))


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        for attr in ['scheme', 'hostname', 'pathsegs', 'querysegs',
                     'fragment', 'port']:
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
        Get the query segments.
        """
        return [y is None and x or '='.join((x,y))
                for (x,y) in self.querysegs]


    @property
    def netloc(self):
        """
        The network location as a unicode string.
        """
        if self.port == _schemeDefaultPorts.get(self.scheme):
            return self.hostname
        else:
            return u"{host}:{port}".format(host=self.hostname,
                                           port=self.port)


    def replace(self, scheme=_unspecified, hostname=_unspecified,
                pathsegs=_unspecified, querysegs=_unspecified,
                fragment=_unspecified, port=_unspecified):
        """
        Make a new instance of C{self.__class__}, passing along the given
        arguments to its constructor.

        @param scheme: the scheme of the new URL; if unspecified, the scheme of
            this URL.

        @param hostname: the hostname of the new URL; if unspecified, the
            hostname of this URL.

        @param pathsegs: the path segments of the new URL; if unspecified, the
            path segments of this URL.

        @param querysegs: the query elements of the new URL; if unspecified,
            the query segments of this URL.

        @param fragment: the fragment of the new URL; if unspecified, the query
            segments of this URL.

        @param port: the netloc of the new URL; if unspecified, the netloc of
            this URL.
        """
        return self.__class__(
            scheme=_optional(scheme, self.scheme),
            hostname=_optional(hostname, self.hostname),
            pathsegs=_optional(pathsegs, self.pathsegs),
            querysegs=_optional(querysegs, self.querysegs),
            fragment=_optional(fragment, self.fragment),
            port=_optional(port, self.port),
        )


    def fromString(cls, s):
        """
        Parse the given string into a URL object.

        Relative path references are not supported.

        @param s: a valid URI or IRI
        @type s: L{unicode} or ASCII L{str}

        @return: the parsed representation of C{s}
        @rtype: L{URL}
        """
        (scheme, netloc, pathsegs, querysegs, fragment) = parseIRI(s)
        # We don't store the leading u'' segment.
        if not pathsegs.pop(0) == u'':
            raise NotImplementedError(
                'relative path references not supported: %r' % (s,))
        split = netloc.split(":")
        if len(split) == 2:
            hostname, port = split
            port = int(port)
        else:
            hostname, port = split[0], None
        return cls(scheme, hostname, pathsegs, querysegs, fragment, port)
    fromString = classmethod(fromString)

    # Path manipulations:


    def sibling(self, path):
        """
        Construct a url where the given path segment is a sibling of this url.
        """
        if not isinstance(path, unicode):
            raise TypeError("Given path must be unicode.")
        l = self.pathsegs[:]
        l[-1] = path
        return self.replace(pathsegs=l)


    def child(self, path):
        """
        Construct a url where the given path segment is a child of this url.
        """
        if not isinstance(path, unicode):
            raise TypeError("Given path must be unicode.")
        l = self.pathsegs[:]
        if l[-1] == u'':
            l[-1] = path
        else:
            l.append(path)
        return self.replace(pathsegs=l)


    def _isRoot(self, pathlist):
        return (pathlist == [u''] or not pathlist)


    def curdir(self):
        """
        Construct a url which is a logical equivalent to '.' of the current
        url.  For example::

            >>> print URL.fromString('http://foo.com/bar').curdir()
            http://foo.com/
            >>> print URL.fromString('http://foo.com/bar/').curdir()
            http://foo.com/bar/
        """
        l = self.pathsegs
        if l[-1] != u'':
            l[-1] = u''
        return self.replace(pathsegs=l)


    def up(self):
        """
        Pop a URL segment from this url.
        """
        l = self.pathsegs[:]
        if l:
            l.pop()
        return self.replace(pathsegs=l)


    def parent(self):
        """
        Construct a url which is the parent of this url's directory; This is
        logically equivalent to '..' of the current url.  For example::

            >>> print URL.fromString('http://foo.com/bar/file').parent()
            http://foo.com/
            >>> print URL.fromString('http://foo.com/bar/dir/').parent()
            http://foo.com/bar/
        """
        l = self.pathsegs[:]
        if not self._isRoot(l) and l[-1] == u'':
            del l[-2]
        else:
            # We are a file, such as http://example.com/foo/bar our parent
            # directory is http://example.com/
            l.pop()
            if self._isRoot(l):
                l.append(u'')
            else: l[-1] = u''
        return self.replace(pathsegs=l)


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

        (scheme, netloc, path, query, fragment) = parseIRI(href)
        leading = path.pop(0)

        if scheme:
            if len(leading):
                # Schemes with relative paths are not well-defined.  RFC 3986
                # calls them a "loophole in prior specifications" that should
                # be avoided, or supported only for backwards compatibility.
                raise NotImplementedError(
                    'scheme with relative path: %r' % (href,))
            return self.replace(scheme, netloc, path, query, fragment)
        else:
            scheme = self.scheme

        if not netloc:
            netloc = self.netloc
            # Merge the paths.
            if len(leading):
                # Relative path:  replace the existing path's last segment.
                path = self.pathsegs[:-1] + [leading] + path
            elif not len(path):
                # No path:  keep the existing path (and if possible, the
                # existing query / fragment).
                path = self.pathsegs
                if not query:
                    query = self.querysegs
                    if not fragment:
                        fragment = self.fragment
            # (Otherwise, the path is absolute, replacing the existing path.)
        else:
            # If the netloc (authority) is present, only absolute paths should
            # be possible.
            assert not len(leading), '%r: relative path with netloc?' % (href,)

        path = normURLPath(path)
        return self.replace(scheme, netloc, path, query, fragment)

    # FIXME: here we call str() on query arg values: is this right?


    def add(self, name, value=None):
        """
        Add a query argument with the given value None indicates that the
        argument has no value
        """
        if (not isinstance(name, unicode) or
            not isinstance(value, (unicode, None.__class__))):
            raise TypeError("name and value must be unicode.")
        return self.replace(querysegs=self.querysegs + [(name, value)])


    def setQueryParam(self, name, value=None):
        """
        Remove all existing occurrences of the query argument 'name', *if it
        exists*, then add the argument with the given value.

        C{None} indicates that the argument has no value.
        """
        if (not isinstance(name, unicode) or
            not isinstance(value, (unicode, None.__class__))):
            raise TypeError("name and value must be unicode.")
        ql = self.querysegs[:]
        # Preserve the original position of the query key in the list
        i = 0
        for (k, v) in ql:
            if k == name:
                break
            i += 1
        q = filter(lambda x: x[0] != name, ql)
        q.insert(i, (name, value))
        return self.replace(querysegs=q)


    def remove(self, name):
        """
        Remove all query arguments with the given name.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        return self.replace(filter(lambda x: x[0] != name, self.querysegs))


    def clear(self, name=None):
        """
        Remove all existing query arguments.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        if name is None:
            q = []
        else:
            q = filter(lambda x: x[0] != name, self.querysegs)
        return self.replace(querysegs=q)


    def __str__(self):
        # Note:  self.pathsegs is stored with an implied leading u'' segment;
        # add it back in before passing to unparseIRI.
        return unparseIRI((self.scheme, self.netloc, [u'']+self.pathsegs,
                           self.querysegs, self.fragment))


    def __repr__(self):
        return (
            '%s(scheme=%r, hostname=%r, pathsegs=%r, querysegs=%r, '
            'fragment=%r, port=%r)'
            % (type(self).__name__,
               self.scheme,
               self.hostname,
               self.pathsegs,
               self.querysegs,
               self.fragment,
               self.port))



def normURLPath(pathSegs):
    """
    Normalise the URL path by resolving segments of '.' and '..'.

    @param pathSegs: list of path segments

    @see: RFC 3986 section 5.2.4, Remove Dot Segments
    """
    segs = []

    for seg in pathSegs:
        if seg == u'.':
            pass
        elif seg == u'..':
            if segs:
                segs.pop()
        else:
            segs.append(seg)

    if pathSegs[-1:] in ([u'.'],[u'..']):
        segs.append(u'')

    return segs
