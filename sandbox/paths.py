
# submitted for inclusion in twisted.python

import os
from os.path import isdir, isabs, isfile, exists, normpath, abspath
from os.path import split as splitpath
from os.path import join as joinpath
from os import sep as slash

class InsecurePath(Exception):
    pass

class FilesystemPath:
    """Immutable filesystem path.
    """
    def __init__(self, path, abs=None):
        if abs is None:
            self.path = normpath(path)
            self.abs = abspath(self.path)
        else:
            self.path = path
            self.abs = abs

    def child(self, path, allowDotDot=0):
        norm = normpath(path)
        if os.sep in norm:
            raise InsecurePath()
        newpath = normpath(joinpath(self.path, norm))
        newabs = abspath(newpath)
        if not newabs.startswith(self.abs):
            raise InsecurePath()
        return FilesystemPath(newpath, newabs)

    def open(self, mode='r'):
        return open(self.path, mode+'b')

    def exists(self):
        return exists(self.path)

    def isabs(self):
        return isabs(self.path)

    def isdir(self):
        return isdir(self.path)

    def __str__(self):
        return self.path

    def __repr__(self):
        return 'FilesystemPath(%r)' % self.path

    def __hash__(self):
        return hash(self.path) + 1

    def __cmp__(self, other):
        return cmp(self.__str__(), other)


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

    def fromString(st):
        t = urlparse.urlsplit(st)
        u = URLPath(*t)
        return u

    def _pathMod(self, newpath, keepQuery):
        if keepQuery:
            query = self.query
        else:
            query = ''
        return URLPath(self.scheme,
                        self.netloc,
                        newpath,
                        query)

    def sibling(self, path, keepQuery=0):
        l = self.pathList()
        l[-1] = path
        newpath = '/'.join(l)
        return self._pathMod(path, keepQuery)

    def child(self, path, keepQuery=0):
        l = self.pathList()
        l.append(path)
        newpath = '/'.join(l)
        return self._pathMod(path, keepQuery)

    def parent(self, keepQuery=0):
        l = self.pathList()
        l[-2:] = []
        newpath = '/'.join(l)
        return self._pathMod(newpath, keepQuery)

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
                l = self.path.split('/')
                l[-1] = path
                path = '/'.join(l)
        
        return URLPath(scheme,
                        netloc,
                        path,
                        query,
                        fragment)

    fromString = staticmethod(fromString)
    
    def __str__(self):
        x = urlparse.urlunsplit((
            self.scheme, self.netloc, self.path,
            self.query, self.fragment))
        return x

    def __repr__(self):
        return repr(self.__dict__)

def test():
    fs = FilesystemPath('/')
    print fs.child('hello')
    print fs.child('hello').child('goodbye')
    fs = FilesystemPath('')
    print fs.child('hello').child('goodbye')
    try:
        print fs.child('..')
    except InsecurePath:
        pass
    else:
        raise 'this is definitely insecure'
    hp = URLPath.fromString('http://www.twistedmatrix.com:8080/')
    print hp
    print repr(hp)
    print hp.click('test#what').click('aaa?a').click('http://shazbot.com').click('ghngh')
    shz = hp.click('aaa').click("?aaa").click("#aaa").click("?yyy=zzz")
    print shz.sibling('bbb')


if __name__ == '__main__':
    test()
