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
from twisted.python import filepath
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
        self.created_time = time.time()
    
    def render(self, ctx):
        response = http.Response(responsecode.OK, stream=self.data)
        response.headers.setRawHeaders("content-type", (self.type, ))
        response.headers.setHeader('etag',
            http_headers.ETag("%X-%X" % (self.created_time, hash(self.data)),
                              weak=(time.time() - self.created_time <= 1)))
        
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
            self.processors = dict([
                (key.lower(), value)
                for key, value in processors.items()
                ])
            
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
            processor = self.processors.get(fpath.splitext()[1].lower())
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
            return responsecode.NOT_FOUND

        if self.fp.isdir():
            # If this is a directory, redirect
            return http.Response(
                responsecode.MOVED_PERMANENTLY,
                {'location': request.unparseURL(path=request.path+'/')})

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

    def listNames(self):
        if not self.fp.isdir():
            return []
        directory = self.fp.listdir()
        directory.sort()
        return directory

    def createSimilarFile(self, path):
        return self.__class__(path, self.defaultType, self.ignoredExts,
                              self.processors, self.indexNames[:])


import md5

class FileSaver(resource.PostableResource):
    allowedTypes = (http_headers.MimeType('text', 'plain'),
                    http_headers.MimeType('text', 'html'),
                    http_headers.MimeType('text', 'css'))
    
    def __init__(self, destination, expectedFields=[], allowedTypes=None, maxBytes=1000000, permissions=0644):
        self.destination = destination
        self.allowedTypes = allowedTypes or self.allowedTypes
        self.maxBytes = maxBytes
        self.expectedFields = expectedFields
        self.permissions = permissions

    def makeUniqueName(self, filename):
        """called when a unique filename is needed
        """

        u = md5.new(filename)
        u.update(str(time.time()))
        ext = os.path.splitext(filename)[1]
        return os.path.join(self.destination, u.hexdigest() + ext)

    def isWriteable(self, filename, mimetype, filestream):
        """returns True if it's "safe" to write this file,
        otherwise it raises an exception
        """
        
        if filestream.length > self.maxBytes:
            raise IOError("%s: File exceeds maximum length (%d > %d)" % (filename,
                                                                         filestream.length,
                                                                         self.maxBytes))

        if os.path.exists(filename):
            # This should really never happen
            raise IOError("%s: File already exists" % (filename,))
 
        if mimetype not in self.allowedTypes:
            raise IOError("%s: File type not allowed %s" % (filename, mimetype))
        
        return True
    
    def writeFile(self, filename, mimetype, fileobject):
        """does the I/O dirty work after it calls isWriteable to make
        sure it's safe to write this file
        """
        outname = self.makeUniqueName(os.path.join(self.destination, filename))
        filestream = stream.FileStream(fileobject)

        if self.isWriteable(outname, mimetype, filestream):
            fd = os.fdopen(os.open(outname, os.O_WRONLY | os.O_CREAT,
                                   self.permissions), 'w', 0)

            stream.readIntoFile(filestream, fd)

        return outname

    def render(self, ctx):
        content = ["<html><body>"]

        req = iweb.IRequest(ctx)

        if req.files:
            for fieldName in req.files:
                if fieldName in self.expectedFields:
                    try:
                        outname = self.writeFile(*req.files[fieldName])
                        content.append("Saved file %s<br />" % outname)
                        
                    except IOError, err:
                        content.append(str(err) + "<br />")
                else:
                    content.append("%s is not a valid field" % fieldName)

        else:
            content.append("No files given")

        content.append("</body></html>")

        return http.Response(responsecode.OK, {}, stream='\n'.join(content))


# FIXME: hi there I am a broken class
# """I contain AsIsProcessor, which serves files 'As Is'
#    Inspired by Apache's mod_asis
# """
# 
# class ASISProcessor:
#     implements(iweb.IResource)
#     
#     def __init__(self, path):
#         self.path = path
# 
#     def renderHTTP(self, request):
#         request.startedWriting = 1
#         return File(self.path)
# 
#     def locateChild(self, request):
#         return None, ()

# Test code
if __name__ == '__builtin__':
    # Running from twistd -y
    from twisted.application import service, strports
    from twisted.web2 import server
    res = File('/')
    application = service.Application("demo")
    s = strports.service('8080', server.Site(res))
    s.setServiceParent(application)
