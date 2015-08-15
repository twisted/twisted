# -*- test-case-name: twisted.test.test_urlpath -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{URLPath}, a representation of a URL.
"""

from __future__ import division, absolute_import

from twisted.python.compat import urllib_parse as urlparse, urlunquote


class URLPath(object):
    """
    A representation of a URL.

    @ivar scheme: The scheme of the URL (e.g. 'http').
    @type scheme: L{bytes}
    @ivar netloc: The network location ("host").
    @type netloc: L{bytes}
    @ivar path: The path on the network location.
    @type path: L{bytes}
    @ivar query: The query argument (the portion after ? in the URL).
    @type query: L{bytes}
    @ivar fragment: The page fragment (the portion after # in the URL).
    @type fragment: L{bytes}
    """
    def __init__(self, scheme=b'', netloc=b'localhost', path=b'',
                 query=b'', fragment=b''):
        self.scheme = scheme or b'http'
        self.netloc = netloc
        self.path = path or b'/'
        self.query = query
        self.fragment = fragment

    _qpathlist = None
    _uqpathlist = None

    def pathList(self, unquote=False, copy=True):
        if self._qpathlist is None:
            self._qpathlist = self.path.split(b'/')
            self._uqpathlist = map(urlunquote, self._qpathlist)
        if unquote:
            result = self._uqpathlist
        else:
            result = self._qpathlist
        if copy:
            return result[:]
        else:
            return result


    @classmethod
    def fromString(klass, url):
        """
        Make a L{URLPath} from a L{str}.

        @param url: A L{str} representation of a URL.
        @rtype: L{URLPath}
        """
        assert isinstance(url, str), "'url' must be a str."
        url = url.encode('utf-8')
        parts = urlparse.urlsplit(url)
        return klass(*parts)


    @classmethod
    def fromBytes(klass, url):
        """
        Make a L{URLPath} from a L{bytes}.

        @param url: A L{bytes} representation of a URL.
        @rtype: L{URLPath}

        @since: 15.4
        """
        assert isinstance(url, bytes), "'url' must be bytes."
        parts = urlparse.urlsplit(url)
        return klass(*parts)


    @classmethod
    def fromRequest(klass, request):
        return klass.fromBytes(request.prePathURL())


    def _pathMod(self, newpathsegs, keepQuery):
        if keepQuery:
            query = self.query
        else:
            query = b''
        return URLPath(self.scheme,
                       self.netloc,
                       b'/'.join(newpathsegs),
                       query)


    def sibling(self, path, keepQuery=False):
        l = self.pathList()
        l[-1] = path
        return self._pathMod(l, keepQuery)


    def child(self, path, keepQuery=False):
        l = self.pathList()
        if l[-1] == b'':
            l[-1] = path
        else:
            l.append(path)
        return self._pathMod(l, keepQuery)


    def parent(self, keepQuery=False):
        l = self.pathList()
        if l[-1] == b'':
            del l[-2]
        else:
            # We are a file, such as http://example.com/foo/bar
            # our parent directory is http://example.com/
            l.pop()
            l[-1] = b''
        return self._pathMod(l, keepQuery)


    def here(self, keepQuery=0):
        l = self.pathList()
        if l[-1] != b'':
            l[-1] = b''
        return self._pathMod(l, keepQuery)


    def click(self, st):
        """
        Return a path which is the URL where a browser would presumably take
        you if you clicked on a link with an HREF as given.
        """
        scheme, netloc, path, query, fragment = urlparse.urlsplit(st)
        if not scheme:
            scheme = self.scheme
        if not netloc:
            netloc = self.netloc
            if not path:
                path = self.path
                if not query:
                    query = self.query
            elif path[0] != b'/':
                l = self.pathList()
                l[-1] = path
                path = b'/'.join(l)

        return URLPath(scheme,
                        netloc,
                        path,
                        query,
                        fragment)


    def __str__(self):
        x = urlparse.urlunsplit((
            self.scheme, self.netloc, self.path, self.query, self.fragment))

        if not isinstance(x, str):
            x = x.decode('utf8')

        return x


    def __repr__(self):
        return ('URLPath(scheme=%r, netloc=%r, path=%r, query=%r, fragment=%r)'
                % (self.scheme, self.netloc, self.path, self.query,
                   self.fragment))
