# -*- test-case-name: nevow.test.test_url -*-
# Copyright (c) 2004-2007 Divmod.
# See LICENSE for details.

"""
URL parsing, construction and rendering.

@see: RFC 3986, Uniform Resource Identifier (URI): Generic Syntax
@see: RFC 3987, Internationalized Resource Identifiers

XXX what about domain names, do we need to do IDNA?
"""

import weakref
import urlparse
import urllib

from zope.interface import implements


# RFC 3986 section 2.2, Reserved Characters
gen_delims = ':/?#[]@'
sub_delims = "!$&'()*+,;="


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

    This avoids percent-encoding characters in L{sub_delims} and C{':@'}.

    @see: RFC 3986 section 3.3, Path
    """
    return iriencode(s, unencoded=sub_delims + ':@')



_queryfield_safe = ((sub_delims + ':@/?')
                    .replace('&', '')
                    .replace('=', '')
                    .replace('+', ''))

def iriencodeQuery(s):
    """
    L{iriencode} convenience wrapper for x-www-form-urlencoded query fields.

    This is like L{iriencodeFragment}, but without C{'&=+'}.
    """
    return iriencode(s, unencoded=_queryfield_safe)



def iriencodeFragment(s):
    """
    L{iriencode} convenience wrapper for fragment components.

    This is like L{iriencodePath}, but with the addition of C{'/?'}.

    @see: RFC 3986 section 3.5, Fragment
    """
    return iriencode(s, unencoded=sub_delims + ':@/?')



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
    # Note:  urllib.unquote interprets percent-encoded octets in unicode strings
    # as Unicode codepoints (effectively decoding them as Latin1), so we cannot
    # pass it unicode strings directly.
    # It doesn't change non-percent-encoded octets in strings, though, so we can
    # encode unicode strings to UTF-8 first:  decoding the result from UTF-8
    # then restores the original Unicode characters in addition to the ones that
    # were percent-encoded.
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
    if x is not None:
        return f(x)

def parseIRI(s):
    """
    Parse a URI/IRI into its components.

    The URI is split into five major components:  I{scheme}, I{netloc}, I{path},
    I{query}, and I{fragment}.

    The I{path} and I{query} components are further parsed:

        I{path} is split into a list of segments, such that a path containing
        I{N} C{'/'} separators will always have I{N+1} segments.  A leading
        segment of C{u''} indicates an absolute path reference;  otherwise, the
        path is relative (this implies that I{netloc} is absent).

        I{query} is split into a list of key and (optional) value fields.
        (see L{unquerify})

    All returned components are fully percent-decoded to L{unicode} strings.

    @return: C{(scheme, netloc, pathsegs, querysegs, fragment)}, per above
    """
    (scheme, netloc, path, query, fragment) = urlparse.urlsplit(s)
    pathsegs = map(iridecode, path.split('/'))
    querysegs = [(iridecode(k), _maybe(iridecode, v))
                 for (k, v) in unquerify(query)]
    if isinstance(netloc, str) or netloc.startswith(u"xn-"):
        netloc = netloc.decode("idna")
    return (iridecode(scheme),
            netloc,
            pathsegs,
            querysegs,
            iridecode(fragment))



def unparseIRI((scheme, netloc, pathsegs, querysegs, fragment)):
    """
    Format a URI/IRI from its components.

    See L{parseIRI};  this is the inverse.
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



class URL(object):
    """
    Represents a URL (actually, an IRI) and provides a convenient API for
    modifying its parts.

    A URL is split into a number of distinct parts: scheme, netloc (domain
    name), path segments, query parameters and fragment identifier.

    Methods are provided to modify many of the parts of the URL, especially
    the path and query parameters. Values can be passed to methods as-is;
    encoding and escaping is handled automatically.

    There preferred way of creating a URL is to call fromString, a class
    method that parses the string format of URLs.

    URL subclasses with different constructor signatures should override
    L{cloneURL} to ensure that the numerous instance methods which return
    copies do so correctly.  Additionally, the L{fromString} method will need
    to be overridden.

    The following attributes are always stored and passed to __init__ in
    decoded form (that is, as C{unicode}, without any
    percent-encoding). C{str} objects should never be passed to C{__init__}!

    @ivar scheme: the URI scheme
    @type scheme: C{unicode}

    @ivar netloc: the host (and possibly port)
    @type netloc: C{unicode}

    @ivar pathsegs: the path segments
    @type pathsegs: list of C{unicode}

    @ivar querysegs: the query parameters, as name-value pairs
    @type querysegs: list of pairs of C{unicode} (or C{None}, for values)

    @ivar fragment: the fragment identifier
    @type fragment: C{unicode}
    """

    def __init__(self, scheme=u'http', netloc=u'', pathsegs=None,
                 querysegs=None, fragment=None):
        def _unicodify(s):
            if not isinstance(s, (unicode, None.__class__)):
                raise TypeError("%r is not unicode" % (s,))
            return s
        self.scheme = _unicodify(scheme)
        self.netloc = _unicodify(netloc)
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


    def path(self):
        """
        The percent-encoded path component of this URL.

        @type: L{str}
        """
        return '/'.join(map(iriencodePath, self.pathsegs))
    path = property(path)


    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        for attr in ['scheme', 'netloc', 'pathsegs', 'querysegs', 'fragment']:
            if getattr(self, attr) != getattr(other, attr):
                return False
        return True


    def __ne__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return not self.__eq__(other)


    query = property(
        lambda self: [y is None and x or '='.join((x,y))
            for (x,y) in self.querysegs]
        )

    def _pathMod(self, newpathsegs, newqueryparts):
        return self.cloneURL(self.scheme,
                             self.netloc,
                             newpathsegs,
                             newqueryparts,
                             self.fragment)


    def cloneURL(self, scheme, netloc, pathsegs, querysegs, fragment):
        """
        Make a new instance of C{self.__class__}, passing along the given
        arguments to its constructor.
        """
        return self.__class__(scheme, netloc, pathsegs, querysegs, fragment)


    ## class methods used to build URL objects ##

    def fromString(cls, s):
        """
        Parse the given string into a URL object.

        Relative path references are not supported.

        @param s: a valid URI or IRI
        @type s: L{unicode} or ASCII L{str}
        """
        (scheme, netloc, pathsegs, querysegs, fragment) = parseIRI(s)
        # We don't store the leading u'' segment.
        if not pathsegs.pop(0) == u'':
            raise NotImplementedError(
                'relative path references not supported: %r' % (s,))
        return cls(scheme, netloc, pathsegs, querysegs, fragment)
    fromString = classmethod(fromString)


    ## path manipulations ##

    def pathList(self, copy=True):
        """
        Return C{self.pathsegs}.

        @param copy:  if true, return a copy
        @type copy: bool
        """
        result = self.pathsegs
        if copy:
            result = result[:]
        return result


    def sibling(self, path):
        """
        Construct a url where the given path segment is a sibling of this url.
        """
        if not isinstance(path, unicode):
            raise TypeError("Given path must be unicode.")
        l = self.pathList()
        l[-1] = path
        return self._pathMod(l, self.queryList(0))


    def child(self, path):
        """
        Construct a url where the given path segment is a child of this url.
        """
        if not isinstance(path, unicode):
            raise TypeError("Given path must be unicode.")
        l = self.pathList()
        if l[-1] == u'':
            l[-1] = path
        else:
            l.append(path)
        return self._pathMod(l, self.queryList(0))


    def _isRoot(self, pathlist):
        return (pathlist == [u''] or not pathlist)


    def curdir(self):
        """
        Construct a url which is a logical equivalent to '.'  of the current
        url. For example:

        >>> print URL.fromString('http://foo.com/bar').curdir()
        http://foo.com/
        >>> print URL.fromString('http://foo.com/bar/').curdir()
        http://foo.com/bar/
        """
        l = self.pathList()
        if l[-1] != u'':
            l[-1] = u''
        return self._pathMod(l, self.queryList(0))


    def up(self):
        """
        Pop a URL segment from this url.
        """
        l = self.pathList()
        if len(l):
            l.pop()
        return self._pathMod(l, self.queryList(0))


    def parentdir(self):
        """
        Construct a url which is the parent of this url's directory;
        This is logically equivalent to '..' of the current url.
        For example:

        >>> print URL.fromString('http://foo.com/bar/file').parentdir()
        http://foo.com/
        >>> print URL.fromString('http://foo.com/bar/dir/').parentdir()
        http://foo.com/bar/
        """
        l = self.pathList()
        if not self._isRoot(l) and l[-1] == u'':
            del l[-2]
        else:
            # we are a file, such as http://example.com/foo/bar our
            # parent directory is http://example.com/
            l.pop()
            if self._isRoot(l):
                l.append(u'')
            else: l[-1] = u''
        return self._pathMod(l, self.queryList(0))


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
                # calls them a "loophole in prior specifications" that should be
                # avoided, or supported only for backwards compatibility.
                raise NotImplementedError(
                    'scheme with relative path: %r' % (href,))
            return self.cloneURL(scheme, netloc, path, query, fragment)
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
        return self.cloneURL(scheme, netloc, path, query, fragment)


    ## query manipulation ##

    def queryList(self, copy=True):
        """
        Return C{self.querysegs}.

        @param copy:  if true, return a copy
        @type copy: bool
        """
        if copy:
            return self.querysegs[:]
        return self.querysegs


    # FIXME: here we call str() on query arg values: is this right?

    def add(self, name, value=None):
        """
        Add a query argument with the given value None indicates that the
        argument has no value
        """
        if (not isinstance(name, unicode) or
            not isinstance(value, (unicode, None.__class__))):
            raise TypeError("name and value must be unicode.")
        q = self.queryList()
        q.append((name, value))
        return self._pathMod(self.pathList(copy=False), q)


    def replace(self, name, value=None):
        """
        Remove all existing occurrences of the query argument 'name', *if it
        exists*, then add the argument with the given value.

        C{None} indicates that the argument has no value.
        """
        if (not isinstance(name, unicode) or
            not isinstance(value, (unicode, None.__class__))):
            raise TypeError("name and value must be unicode.")
        ql = self.queryList(False)
        ## Preserve the original position of the query key in the list
        i = 0
        for (k, v) in ql:
            if k == name:
                break
            i += 1
        q = filter(lambda x: x[0] != name, ql)
        q.insert(i, (name, value))
        return self._pathMod(self.pathList(copy=False), q)


    def remove(self, name):
        """
        Remove all query arguments with the given name.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        return self._pathMod(
            self.pathList(copy=False),
            filter(
                lambda x: x[0] != name, self.queryList(False)))


    def clear(self, name=None):
        """
        Remove all existing query arguments.
        """
        if not isinstance(name, (unicode, None.__class__)):
            raise TypeError("name  must be unicode.")
        if name is None:
            q = []
        else:
            q = filter(lambda x: x[0] != name, self.queryList(False))
        return self._pathMod(self.pathList(copy=False), q)


    ## scheme manipulation ##

    def secure(self, secure=True, port=None):
        """
        Modify the scheme to https/http and return the new URL.

        @param secure: choose between https and http, default to True (https)
        @param port: port, override the scheme's normal port
        """

        # Choose the scheme and default port.
        if secure:
            scheme, defaultPort = u'https', 443
        else:
            scheme, defaultPort = u'http', 80

        # Rebuild the netloc with port if not default.
        netloc = self.netloc.split(u':',1)[0]
        if port is not None and port != defaultPort:
            netloc = u'%s:%d' % (netloc, port)

        return self.cloneURL(
            scheme, netloc, self.pathsegs, self.querysegs, self.fragment)


    ## fragment/anchor manipulation

    def anchor(self, anchor=None):
        """
        Modify the fragment/anchor and return a new URL. An anchor of
        C{None} (the default) or C{''} (the empty string) will remove the
        current anchor.
        """
        return self.cloneURL(
            self.scheme, self.netloc, self.pathsegs, self.querysegs, anchor)


    ## object protocol override ##

    def __str__(self):
        # Note:  self.pathsegs is stored with an implied leading u'' segment;
        # add it back in before passing to unparseIRI.
        return unparseIRI((self.scheme, self.netloc, [u'']+self.pathsegs,
                           self.querysegs, self.fragment))


    def __repr__(self):
        return (
            '%s(scheme=%r, netloc=%r, pathsegs=%r, querysegs=%r, fragment=%r)'
            % (type(self).__name__,
               self.scheme,
               self.netloc,
               self.pathsegs,
               self.querysegs,
               self.fragment))


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
