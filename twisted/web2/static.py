# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I deal with static resources.
"""

# System Imports
import os, time
import tempfile

# Sibling Imports
from twisted.web2 import http_headers, resource
from twisted.web2 import http, iweb, stream, responsecode, server, dirlist

# Twisted Imports
from twisted.python import filepath
from twisted.internet.defer import maybeDeferred
from zope.interface import implements

class MetaDataMixin(object):
    """
    Mix-in class for L{iweb.IResource} which provides methods for accessing resource
    metadata specified by HTTP.
    """
    def etag(self):
        """
        @return: The current etag for the resource if available, None otherwise.
        """
        return None

    def lastModified(self):
        """
        @return: The last modified time of the resource if available, None otherwise.
        """
        return None

    def creationDate(self):
        """
        @return: The creation date of the resource if available, None otherwise.
        """
        return None

    def contentLength(self):
        """
        @return: The size in bytes of the resource if available, None otherwise.
        """
        return None

    def contentType(self):
        """
        @return: The MIME type of the resource if available, None otherwise.
        """
        return None

    def contentEncoding(self):
        """
        @return: The encoding of the resource if available, None otherwise.
        """
        return None

    def displayName(self):
        """
        @return: The display name of the resource if available, None otherwise.
        """
        return None

    def exists(self):
        """
        @return: True if the resource exists on the server, False otherwise.
        """
        return True

class StaticRenderMixin(resource.RenderMixin, MetaDataMixin):
    def checkPreconditions(self, request):
        # This code replaces the code in resource.RenderMixin
        if request.method not in ("GET", "HEAD"):
            http.checkPreconditions(
                request,
                entityExists = self.exists(),
                etag = self.etag(),
                lastModified = self.lastModified(),
            )

        # Check per-method preconditions
        method = getattr(self, "preconditions_" + request.method, None)
        if method:
            return method(request)

    def renderHTTP(self, request):
        """
        See L{resource.RenderMixIn.renderHTTP}.

        This implementation automatically sets some headers on the response
        based on data available from L{MetaDataMixin} methods.
        """
        def setHeaders(response):
            response = iweb.IResponse(response)

            # Don't provide additional resource information to error responses
            if response.code < 400:
                # Content-* headers refer to the response content, not
                # (necessarily) to the resource content, so they depend on the
                # request method, and therefore can't be set here.
                for (header, value) in (
                    ("etag", self.etag()),
                    ("last-modified", self.lastModified()),
                ):
                    if value is not None:
                        response.headers.setHeader(header, value)

            return response

        def onError(f):
            # If we get an HTTPError, run its response through setHeaders() as
            # well.
            f.trap(http.HTTPError)
            return setHeaders(f.value.response)

        d = maybeDeferred(super(StaticRenderMixin, self).renderHTTP, request)
        return d.addCallbacks(setHeaders, onError)

class Data(resource.Resource):
    """
    This is a static, in-memory resource.
    """
    def __init__(self, data, type):
        self.data = data
        self.type = http_headers.MimeType.fromString(type)
        self.created_time = time.time()

    def etag(self):
        lastModified = self.lastModified()
        return http_headers.ETag("%X-%X" % (lastModified, hash(self.data)),
                                 weak=(time.time() - lastModified <= 1))

    def lastModified(self):
        return self.creationDate()

    def creationDate(self):
        return self.created_time

    def contentLength(self):
        return len(self.data)

    def contentType(self):
        return self.type

    def render(self, req):
        return http.Response(
            responsecode.OK,
            http_headers.Headers({'content-type': self.contentType()}),
            stream=self.data)


class File(StaticRenderMixin):
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
    implements(iweb.IResource)

    def _getContentTypes(self):
        if not hasattr(File, "_sharedContentTypes"):
            File._sharedContentTypes = loadMimeTypes()
        return File._sharedContentTypes

    contentTypes = property(_getContentTypes)

    contentEncodings = {
        ".gz" : "gzip",
        ".bz2": "bzip2"
        }

    processors = {}

    indexNames = ["index", "index.html", "index.htm", "index.rpy"]

    type = None

    def __init__(self, path, defaultType="text/plain", ignoredExts=(), processors=None, indexNames=None):
        """Create a file with the given path.
        """
        super(File, self).__init__()

        self.putChildren = {}
        self.fp = filepath.FilePath(path)
        # Remove the dots from the path to split
        self.defaultType = defaultType
        self.ignoredExts = list(ignoredExts)
        if processors is not None:
            self.processors = dict([
                (key.lower(), value)
                for key, value in processors.items()
                ])

        if indexNames is not None:
            self.indexNames = indexNames

    def exists(self):
        return self.fp.exists()

    def etag(self):
        if not self.fp.exists(): return None

        st = self.fp.statinfo

        #
        # Mark ETag as weak if it was modified more recently than we can
        # measure and report, as it could be modified again in that span
        # and we then wouldn't know to provide a new ETag.
        #
        weak = (time.time() - st.st_mtime <= 1)

        return http_headers.ETag(
            "%X-%X-%X" % (st.st_ino, st.st_size, st.st_mtime),
            weak=weak
        )

    def lastModified(self):
        if self.fp.exists():
            return self.fp.getmtime()
        else:
            return None

    def creationDate(self):
        if self.fp.exists():
            return self.fp.getmtime()
        else:
            return None

    def contentLength(self):
        if self.fp.exists():
            if self.fp.isfile():
                return self.fp.getsize()
            else:
                # Computing this would require rendering the resource; let's
                # punt instead.
                return None
        else:
            return None

    def _initTypeAndEncoding(self):
        self._type, self._encoding = getTypeAndEncoding(
            self.fp.basename(),
            self.contentTypes,
            self.contentEncodings,
            self.defaultType
        )

        # Handle cases not covered by getTypeAndEncoding()
        if self.fp.isdir(): self._type = "httpd/unix-directory"

    def contentType(self):
        if not hasattr(self, "_type"):
            self._initTypeAndEncoding()
        return http_headers.MimeType.fromString(self._type)

    def contentEncoding(self):
        if not hasattr(self, "_encoding"):
            self._initTypeAndEncoding()
        return self._encoding

    def displayName(self):
        if self.fp.exists():
            return self.fp.basename()
        else:
            return None

    def ignoreExt(self, ext):
        """Ignore the given extension.

        Serve file.ext if file is requested
        """
        self.ignoredExts.append(ext)

    def directoryListing(self):
        return dirlist.DirectoryLister(self.fp.path,
                                       self.listChildren(),
                                       self.contentTypes,
                                       self.contentEncodings,
                                       self.defaultType)

    def putChild(self, name, child):
        """
        Register a child with the given name with this resource.
        @param name: the name of the child (a URI path segment)
        @param child: the child to register
        """
        self.putChildren[name] = child

    def getChild(self, name):
        """
        Look up a child resource.
        @return: the child of this resource with the given name.
        """
        if name == "":
            return self

        child = self.putChildren.get(name, None)
        if child: return child

        child_fp = self.fp.child(name)
        if child_fp.exists():
            return self.createSimilarFile(child_fp.path)
        else:
            return None

    def listChildren(self):
        """
        @return: a sequence of the names of all known children of this resource.
        """
        children = self.putChildren.keys()
        if self.fp.isdir():
            children += [c for c in self.fp.listdir() if c not in children]
        return children

    def locateChild(self, req, segments):
        """
        See L{IResource}C{.locateChild}.
        """
        # If getChild() finds a child resource, return it
        child = self.getChild(segments[0])
        if child is not None: return (child, segments[1:])

        # If we're not backed by a directory, we have no children.
        # But check for existance first; we might be a collection resource
        # that the request wants created.
        self.fp.restat(False)
        if self.fp.exists() and not self.fp.isdir(): return (None, ())

        # OK, we need to return a child corresponding to the first segment
        path = segments[0]

        if path:
            fpath = self.fp.child(path)
        else:
            # Request is for a directory (collection) resource
            return (self, server.StopTraversal)

        # Don't run processors on directories - if someone wants their own
        # customized directory rendering, subclass File instead.
        if fpath.isfile():
            processor = self.processors.get(fpath.splitext()[1].lower())
            if processor:
                return (
                    processor(fpath.path),
                    segments[1:])

        elif not fpath.exists():
            sibling_fpath = fpath.siblingExtensionSearch(*self.ignoredExts)
            if sibling_fpath is not None:
                fpath = sibling_fpath

        return self.createSimilarFile(fpath.path), segments[1:]

    def renderHTTP(self, req):
        self.fp.restat(False)
        return super(File, self).renderHTTP(req)

    def render(self, req):
        """You know what you doing."""
        if not self.fp.exists():
            return responsecode.NOT_FOUND

        if self.fp.isdir():
            if req.uri[-1] != "/":
                # Redirect to include trailing '/' in URI
                return http.RedirectResponse(req.unparseURL(path=req.path+'/'))
            else:
                ifp = self.fp.childSearchPreauth(*self.indexNames)
                if ifp:
                    # Render from the index file
                    standin = self.createSimilarFile(ifp.path)
                else:
                    # Render from a DirectoryLister
                    standin = dirlist.DirectoryLister(
                        self.fp.path,
                        self.listChildren(),
                        self.contentTypes,
                        self.contentEncodings,
                        self.defaultType
                    )
                return standin.render(req)

        try:
            f = self.fp.open()
        except IOError, e:
            import errno
            if e[0] == errno.EACCES:
                return responsecode.FORBIDDEN
            elif e[0] == errno.ENOENT:
                return responsecode.NOT_FOUND
            else:
                raise

        response = http.Response()
        response.stream = stream.FileStream(f, 0, self.fp.getsize())

        for (header, value) in (
            ("content-type", self.contentType()),
            ("content-encoding", self.contentEncoding()),
        ):
            if value is not None:
                response.headers.setHeader(header, value)

        return response

    def createSimilarFile(self, path):
        return self.__class__(path, self.defaultType, self.ignoredExts,
                              self.processors, self.indexNames[:])


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
        """Called when a unique filename is needed.

        filename is the name of the file as given by the client.

        Returns the fully qualified path of the file to create. The
        file must not yet exist.
        """

        return tempfile.mktemp(suffix=os.path.splitext(filename)[1], dir=self.destination)

    def isSafeToWrite(self, filename, mimetype, filestream):
        """Returns True if it's "safe" to write this file,
        otherwise it raises an exception.
        """

        if filestream.length > self.maxBytes:
            raise IOError("%s: File exceeds maximum length (%d > %d)" % (filename,
                                                                         filestream.length,
                                                                         self.maxBytes))

        if mimetype not in self.allowedTypes:
            raise IOError("%s: File type not allowed %s" % (filename, mimetype))

        return True

    def writeFile(self, filename, mimetype, fileobject):
        """Does the I/O dirty work after it calls isSafeToWrite to make
        sure it's safe to write this file.
        """
        filestream = stream.FileStream(fileobject)

        if self.isSafeToWrite(filename, mimetype, filestream):
            outname = self.makeUniqueName(filename)

            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)

            fileobject = os.fdopen(os.open(outname, flags, self.permissions), 'wb', 0)
                
            stream.readIntoFile(filestream, fileobject)

        return outname

    def render(self, req):
        content = ["<html><body>"]

        if req.files:
            for fieldName in req.files:
                if fieldName in self.expectedFields:
                    for finfo in req.files[fieldName]:
                        try:
                            outname = self.writeFile(*finfo)
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

##
# Utilities
##

dangerousPathError = http.HTTPError(responsecode.NOT_FOUND) #"Invalid request URL."

def isDangerous(path):
    return path == '..' or '/' in path or os.sep in path

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

##
# Test code
##

if __name__ == '__builtin__':
    # Running from twistd -y
    from twisted.application import service, strports
    res = File('/')
    application = service.Application("demo")
    s = strports.service('8080', server.Site(res))
    s.setServiceParent(application)
