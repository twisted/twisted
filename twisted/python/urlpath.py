# -*- test-case-name: twisted.test.test_paths -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

import urlparse
import urllib

class Authority:
    """
    An abstraction of the "authority" section of a URI.

    Term taken from RFC2396.
    """
    def __init__(self, auth):
        self.auth = auth
        auths = auth.split('@')
        if len(auths) == 2:
            userpass = auths.pop(0)
            userpass = userpass.split(':')
            self.user = userpass.pop(0)
            try:
                self.password = userpass.pop(0)
            except:
                self.password = ''
        else:
            self.user = self.password = ''
        hostport = auths[0].split(':')
        self.host = hostport.pop(0) or ''
        try:
            self.port = int(hostport.pop(0))
        except:
            self.port = 0

    def parse(self):
        """
        Return a tuple representing the parts of the authority.
        """
        return (self.user, self.password, self.host, self.port)

    def __str__(self):
        return self.auth

    def __repr__(self):
        return ('Authority(user=%r, password=%r, host=%r, port=%r)'
                % self.parse())
            

class URLPath:
    def __init__(self, scheme='', netloc='localhost', path='',
                 query='', fragment=''):
        self.scheme = scheme or 'http'
        self.netloc = netloc
        self.path = path or '/'
        self.query = query
        self.fragment = fragment
        auth = Authority(netloc)
        self.user, self.password, self.host, self.port = auth.parse()

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

    def _pathMod(self, newpathsegs, keepQuery):
        if keepQuery:
            query = self.query
        else:
            query = ''
        return URLPath(self.scheme,
                        self.netloc,
                        '/'.join(newpathsegs),
                        query)

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

