# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I deal with static resources.
"""

# System Imports
import os, time, stat

# Sibling Imports
from twisted.web2 import http_headers, resource
from twisted.web2 import http, iweb, stream, responsecode

# Twisted Imports
from twisted.python import components, filepath
from twisted.python.util import InsensitiveDict
from twisted.python.runtime import platformType
from zope.interface import implements

dangerousPathError = http.HTTPError(responsecode.NOT_FOUND) #"Invalid request URL."

def isDangerous(path):
    return path == '..' or '/' in path or os.sep in path


class Data(resource.Resource):
    
    """
    This is a static, in-memory resource.
    """
    
    def __init__(self, data, type):
        self.data = data
        self.type = type
    
    def render(self, ctx):
        response = http.Response()
        response.headers.setRawHeaders("content-type", (self.type, ))
        response.stream = stream.MemoryStream(self.data)
        return response

def addSlash(request):
    return "http%s://%s%s/" % (
        request.isSecure() and 's' or '',
        request.getHeader("host"),
        (request.uri.split('?')[0]))

def loadMimeTypes(mimetype_locations=['/etc/mime.types']):
    """
    Multiple file locations containing mime-types can be passed as a list.
    The files will be sourced in that order, overriding mime-types from the
    files sourced beforehand, but only if a new entry explicitly overrides
    the current entry.
    """
    import mimetypes
    # Grab Python's built-in mimetypes dictionary.
    contentTypes = mimetypes.types_map
    # Update Python's semi-erroneous dictionary with a few of the
    # usual suspects.
    contentTypes.update(
        {
            '.conf':  'text/plain',
            '.diff':  'text/plain',
            '.exe':   'application/x-executable',
            '.flac':  'audio/x-flac',
            '.java':  'text/plain',
            '.ogg':   'application/ogg',
            '.oz':    'text/x-oz',
            '.swf':   'application/x-shockwave-flash',
            '.tgz':   'application/x-gtar',
            '.wml':   'text/vnd.wap.wml',
            '.xul':   'application/vnd.mozilla.xul+xml',
            '.py':    'text/plain',
            '.patch': 'text/plain',
        }
    )
    # Users can override these mime-types by loading them out configuration
    # files (this defaults to ['/etc/mime.types']).
    for location in mimetype_locations:
        if os.path.exists(location):
            contentTypes.update(mimetypes.read_mime_types(location))
            
    return contentTypes

def getTypeAndEncoding(filename, types, encodings, defaultType):
    p, ext = os.path.splitext(filename)
    ext = ext.lower()
    if encodings.has_key(ext):
        enc = encodings[ext]
        ext = os.path.splitext(p)[1].lower()
    else:
        enc = None
    type = types.get(ext, defaultType)
    return type, enc


class File(resource.Resource):
    """
    File is a resource that represents a plain non-interpreted file
    (although it can look for an extension like .rpy or .cgi and hand the
    file to a processor for interpretation if you wish). Its constructor
    takes a file path.

    Alternatively, you can give a directory path to the constructor. In this
    case the resource will represent that directory, and its children will
    be files underneath that directory. This provides access to an entire
    filesystem tree with a single Resource.

    If you map the URL 'http://server/FILE' to a resource created as
    File('/tmp'), then http://server/FILE/ will return an HTML-formatted
    listing of the /tmp/ directory, and http://server/FILE/foo/bar.html will
    return the contents of /tmp/foo/bar.html .
    """

    
    contentTypes = loadMimeTypes()

    contentEncodings = {
        ".gz" : "gzip",
        ".bz2": "bzip2"
        }

    processors = {}

    indexNames = ["index", "index.html", "index.htm", "index.trp", "index.rpy"]

    type = None

    def __init__(self, path, defaultType="text/plain", ignoredExts=(), processors=None, indexNames=None):
        """Create a file with the given path.
        """
        self.fp = filepath.FilePath(path)
        # Remove the dots from the path to split
        self.defaultType = defaultType
        self.ignoredExts = list(ignoredExts)
        self.children = {}
        if processors is not None:
            self.processors = processors
        if indexNames is not None:
            self.indexNames = indexNames

    def ignoreExt(self, ext):
        """Ignore the given extension.

        Serve file.ext if file is requested
        """
        self.ignoredExts.append(ext)

    def directoryListing(self):
        from twisted.web2 import dirlist
        return dirlist.DirectoryLister(self.fp.path,
                                       self.listNames(),
                                       self.contentTypes,
                                       self.contentEncodings,
                                       self.defaultType)

    def putChild(self, name, child):
        self.children[name] = child
        
    def locateChild(self, ctx, segments):
        r = self.children.get(segments[0], None)
        if r:
            return r, segments[1:]
        
        path=segments[0]
        
        self.fp.restat()
        
        if not self.fp.isdir():
            return None, ()

        if path:
            fpath = self.fp.child(path)
        else:
            fpath = self.fp.childSearchPreauth(*self.indexNames)
            if fpath is None:
                return self.directoryListing(), segments[1:]

        if not fpath.exists():
            fpath = fpath.siblingExtensionSearch(*self.ignoredExts)
            if fpath is None:
                return None, ()

        # Don't run processors on directories - if someone wants their own
        # customized directory rendering, subclass File instead.
        if fpath.isfile():
            if platformType == "win32":
                # don't want .RPY to be different than .rpy, since that
                # would allow source disclosure.
                processor = InsensitiveDict(self.processors).get(fpath.splitext()[1])
            else:
                processor = self.processors.get(fpath.splitext()[1])
            if processor:
                return (
                    processor(fpath.path),
                    segments[1:])

        return self.createSimilarFile(fpath.path), segments[1:]

    def render(self, ctx):
        """You know what you doing."""
        self.fp.restat()
        request = iweb.IRequest(ctx)
        response = http.Response()
        
        if self.type is None:
            self.type, self.encoding = getTypeAndEncoding(self.fp.basename(),
                                                          self.contentTypes,
                                                          self.contentEncodings,
                                                          self.defaultType)

        if not self.fp.exists():
            return response.NOT_FOUND

        if self.fp.isdir():
            return self.redirectWithSlash(request)

        if self.type:
            response.headers.setRawHeaders('content-type', (self.type,))
        if self.encoding:
            response.headers.setHeader('content-encoding', self.encoding)

        try:
            f = self.fp.open()
        except IOError, e:
            import errno
            if e[0] == errno.EACCES:
                return responsecode.FORBIDDEN
            else:
                raise

        st = os.fstat(f.fileno())
        
        # Be sure it's a regular file.
        if not stat.S_ISREG(st.st_mode):
            return responsecode.FORBIDDEN
        
        #for content-length
        size = st.st_size
        
        response.headers.setHeader('last-modified', st.st_mtime)
        
        # Mark ETag as weak if it was modified recently, as it could
        # be modified again without changing mtime.
        weak = (time.time() - st.st_mtime <= 1)
        
        etag = http_headers.ETag(
            "%X-%X-%X" % (st.st_ino, st.st_size, st.st_mtime),
            weak=weak)
        
        response.headers.setHeader('etag', etag)
        response.headers.setHeader('content-length', size)
        response.stream = stream.FileStream(f, 0, size)
        return response

    def redirectWithSlash(self, request):
        return error.redirect(addSlash(request))

    def listNames(self):
        if not self.fp.isdir():
            return []
        directory = self.fp.listdir()
        directory.sort()
        return directory

    def createSimilarFile(self, path):
        return self.__class__(path, self.defaultType, self.ignoredExts,
                              self.processors, self.indexNames[:])

"""I contain AsIsProcessor, which serves files 'As Is'
   Inspired by Apache's mod_asis
"""

class ASISProcessor:
    implements(iweb.IResource)
    
    def __init__(self, path):
        self.path = path

    def renderHTTP(self, request):
        request.startedWriting = 1
        return File(self.path)

    def locateChild(self, request):
        return FourOhFour(), ()

# Test code
if __name__ == '__builtin__':
    # Running from twistd -y
    from twisted.application import service, strports
    from twisted.web2 import server
    res = File('/')
    application = service.Application("demo")
    s = strports.service('8080', server.Site(res))
    s.setServiceParent(application)
