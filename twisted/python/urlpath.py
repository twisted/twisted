# -*- test-case-name: twisted.python.test.test_urlpath -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{URLPath}, a representation of a URL.
"""

from __future__ import division, absolute_import

from twisted.python.compat import (
    nativeString, unicode, urllib_parse as urlparse, urlunquote
)

from twisted.python.url import URL as _URL


class URLPath(object):
    """
    A representation of a URL.

    @ivar scheme: The scheme of the URL (e.g. 'http').
    @type scheme: L{bytes}

    @ivar netloc: The network location ("host").
    @type netloc: L{bytes}

    @ivar path: The path on the network location.
    @type path: L{bytes}

    @ivar query: The query argument (the portion after ?  in the URL).
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
        self._url = _URL.fromText(
            urlparse.urlunsplit((self.scheme, self.netloc, self.path,
                                 self.query, self.fragment))
            .decode("ascii")
        )


    @classmethod
    def _fromURL(cls, urlInstance):
        """
        Reconstruct all the public instance variables of this L{URLPath} from
        its underlying L{_URL}.

        @param urlInstance: the object to base this L{URLPath} on.
        @type urlInstance: L{_URL}

        @return: a new L{URLPath}
        """
        self = cls.__new__(cls)
        self._url = urlInstance
        self.scheme = self._url.scheme.encode("ascii")
        self.netloc = self._url.authority.encode("ascii")
        self.path = (_URL(pathSegments=self._url.pathSegments).asText()
                     .encode("ascii"))
        self.query = (_URL(queryParameters=self._url.queryParameters).asText()
                      .encode("ascii"))[1:]
        self.fragment = self._url.fragment.encode("ascii")
        return self


    def pathList(self, unquote=False, copy=True):
        """
        Split this URL's path into its components.

        @param unquote: whether to remove %-encoding from the returned strings.

        @param copy: (ignored, do not use)

        @return: The components of C{self.path}
        @rtype: L{list} of L{bytes}
        """
        segments = self._url.pathSegments
        if unquote:
            segments = [urlunquote(segment) for segment in segments]
        else:
            segments = list(segments)
        return [b''] + segments


    @classmethod
    def fromString(klass, url):
        """
        Make a L{URLPath} from a L{str} or L{unicode}.

        @param url: A L{str} representation of a URL.
        @type url: L{str} or L{unicode}.

        @return: a new L{URLPath} derived from the given string.
        @rtype: L{URLPath}
        """
        if not isinstance(url, (str, unicode)):
            raise ValueError("'url' must be a str or unicode")
        url = url.encode('ascii')
        parts = urlparse.urlsplit(url)
        return klass(*parts)


    @classmethod
    def fromBytes(klass, url):
        """
        Make a L{URLPath} from a L{bytes}.

        @param url: A L{bytes} representation of a URL.
        @type url: L{bytes}

        @return: a new L{URLPath} derived from the given L{bytes}.
        @rtype: L{URLPath}

        @since: 15.4
        """
        if not isinstance(url, bytes):
            raise ValueError("'url' must be bytes")
        parts = urlparse.urlsplit(url)
        return klass(*parts)


    @classmethod
    def fromRequest(klass, request):
        """
        Make a L{URLPath} from a L{twisted.web.http.Request}.

        @param request: A L{twisted.web.http.Request} to make the L{URLPath}
            from.

        @return: a new L{URLPath} derived from the given request.
        @rtype: L{URLPath}
        """
        return klass.fromBytes(request.prePathURL())


    def _mod(self, newURL, keepQuery):
        """
        Return a modified copy of C{self} using C{newURL}, keeping the query
        string if C{keepQuery} is C{True}.

        @param newURL: a L{URL} to derive a new L{URLPath} from
        @type newURL: L{URL}

        @param keepQuery: if C{True}, preserve the query parameters from
            C{self} on the new L{URLPath}; if C{False}, give the new L{URLPath}
            no query parameters.
        @type keepQuery: L{bool}

        @return: a new L{URLPath}
        """
        return self._fromURL(
            newURL.replace(fragment=u'',
                           queryParameters=self._url.queryParameters
                           if keepQuery else ())
        )


    def sibling(self, path, keepQuery=False):
        """
        Get the sibling of the current L{URLPath}.  A sibling is a file which
        is in the same directory as the current file.

        @param path: The path of the sibling.
        @type path: L{bytes}

        @param keepQuery: Whether to keep the query parameters on the returned
            L{URLPath}.
        @type: keepQuery: L{bool}

        @return: a new L{URLPath}
        """
        return self._mod(self._url.sibling(path.decode("ascii")), keepQuery)


    def child(self, path, keepQuery=False):
        """
        Get the child of this L{URLPath}.

        @param path: The path of the child.
        @type path: L{bytes}

        @param keepQuery: Whether to keep the query parameters on the returned
            L{URLPath}.
        @type: keepQuery: L{bool}

        @return: a new L{URLPath}
        """
        return self._mod(self._url.child(path.decode("ascii")), keepQuery)


    def parent(self, keepQuery=False):
        """
        Get the parent directory of this L{URLPath}.

        @param keepQuery: Whether to keep the query parameters on the returned
            L{URLPath}.
        @type: keepQuery: L{bool}

        @return: a new L{URLPath}
        """
        return self._mod(self._url.click(u".."), keepQuery)


    def here(self, keepQuery=False):
        """
        Get the current directory of this L{URLPath}.

        @param keepQuery: Whether to keep the query parameters on the returned
            L{URLPath}.
        @type: keepQuery: L{bool}

        @return: a new L{URLPath}
        """
        return self._mod(self._url.click(u"."), keepQuery)


    def click(self, st):
        """
        Return a path which is the URL where a browser would presumably take
        you if you clicked on a link with an HREF as given.

        @param st: A relative URL, to be interpreted relative to C{self} as the
            base URL.
        @type st: L{bytes}

        @return: a new L{URLPath}
        """
        return self._fromURL(self._url.click(st.decode("ascii")))


    def __str__(self):
        """
        The L{str} of a L{URLPath} is its URL text.
        """
        return nativeString(self._url.asText())


    def __repr__(self):
        """
        The L{repr} of a L{URLPath} is an eval-able expression which will
        construct a similar L{URLPath}.
        """
        return ('URLPath(scheme=%r, netloc=%r, path=%r, query=%r, fragment=%r)'
                % (self.scheme, self.netloc, self.path, self.query,
                   self.fragment))
