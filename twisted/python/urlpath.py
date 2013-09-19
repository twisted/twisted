# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#

import urlparse
import urllib



class URLPath:
    def __init__(self, scheme='', netloc='localhost', path='',
                 query='', fragment=''):
        self.scheme = scheme or 'http'
        self.netloc = netloc
        self.path = path or '/'
        self.query = query
        self.fragment = fragment

    _qpathlist = None
    _uqpathlist = None


    def pathList(self, unquote=0, copy=1):
        if self._qpathlist is None:
            self._qpathlist = self.path.split('/')
            self._uqpathlist = map(urllib.unquote, self._qpathlist)
        if unquote:
            result = self._uqpathlist
        else:
            result = self._qpathlist
        if copy:
            return result[:]
        else:
            return result


    def fromString(klass, st):
        t = urlparse.urlsplit(st)
        u = klass(*t)
        return u

    fromString = classmethod(fromString)


    def fromRequest(klass, request):
        return klass.fromString(request.prePathURL())

    fromRequest = classmethod(fromRequest)


    def _pathMod(self, newpathsegs, keepQuery, keepFragment=False):
        """
        Create a new L{URLPath} from a list of path segments and optionally
        this instance's query and fragment.

        @param newpathsegs: A list of path segment strings to use in creating
            the new L{URLPath} object.
        @type newpathsegs: I{iterable}

        @param keepQuery: Flag indicating that the query portion of this
            L{URLPath} should be included in the new instance.
        @type keepQuery: L{bool}

        @param keepFragment: Flag indicating that the fragment portion of this
            L{URLPath} sohuld be included in the new instance.
        @type keepFragment: L{bool}
        """
        if keepQuery:
            query = self.query
        else:
            query = ''
        if keepFragment:
            fragment = self.fragment
        else:
            fragment = ''
        return URLPath(self.scheme,
                        self.netloc,
                        '/'.join(newpathsegs),
                        query,
                        fragment)


    def sibling(self, path, keepQuery=0):
        l = self.pathList()
        l[-1] = path
        return self._pathMod(l, keepQuery)


    def child(self, path, keepQuery=0):
        l = self.pathList()
        if l[-1] == '':
            l[-1] = path
        else:
            l.append(path)
        return self._pathMod(l, keepQuery)


    def parent(self, keepQuery=0):
        l = self.pathList()
        if l[-1] == '':
            del l[-2]
        else:
            # We are a file, such as http://example.com/foo/bar
            # our parent directory is http://example.com/
            l.pop()
            l[-1] = ''
        return self._pathMod(l, keepQuery)


    def clone(self, keepQuery=True, keepFragment=True):
        """
        Get a copy of this path (including the query and fragment by default).

        C{URLPath.fromString('http://example.com/foo/bar?hey=ho').clone(False)}
        is equivalent to C{URLPath.fromString('http://example.com/foo/bar')}.

        @param keepQuery: If C{False} then don't include the query parameters.
        @param keepFragment: If C{False} then don't include the fragment.

        @return: A L{URLPath} identical to me (but without the query portion
            depending on C{keepQuery})
        """
        return self._pathMod(self.pathList(), keepQuery, keepFragment)


    def up(self, keepQuery=0):
        """
        Remove the final URL path segment, and remaining I{/}.

        Counter-intuitively this is the inverse of L{child}, it differs from
        L{parent} in that it removes the final path segment and then any
        remaining I{/}s.

        For instance, the path "up" from C{http://example.com/foo/bar} is
        C{http://example.com/foo} and the path "up" from
        C{http://example.com/foo/} is C{http://example.com/foo}.

        @return: A new L{URLPath} one segment "up" from this path.
        """
        l = self.pathList()
        del l[-1]
        return self._pathMod(l, keepQuery)


    def here(self, keepQuery=0):
        l = self.pathList()
        if l[-1] != '':
            l[-1] = ''
        return self._pathMod(l, keepQuery)


    def click(self, st):
        """Return a path which is the URL where a browser would presumably take
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
            elif path[0] != '/':
                l = self.pathList()
                l[-1] = path
                path = '/'.join(l)
        
        return URLPath(scheme,
                        netloc,
                        path,
                        query,
                        fragment)

    
    def __str__(self):
        x = urlparse.urlunsplit((
            self.scheme, self.netloc, self.path,
            self.query, self.fragment))
        return x


    def __repr__(self):
        return ('URLPath(scheme=%r, netloc=%r, path=%r, query=%r, fragment=%r)'
                % (self.scheme, self.netloc, self.path, self.query, self.fragment))

