# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I deal with static resources.
"""

from __future__ import nested_scopes

# System Imports
import os, stat, string
import cStringIO
import traceback
import warnings
import types
StringIO = cStringIO
del cStringIO
import urllib

# Sibling Imports
from twisted.web import server
from twisted.web import error
from twisted.web import resource
from twisted.web.util import redirectTo

# Twisted Imports
from twisted.web import http
from twisted.python import threadable, log, components, failure, filepath
from twisted.internet import abstract, interfaces, defer
from twisted.spread import pb
from twisted.persisted import styles
from twisted.python.util import InsensitiveDict
from twisted.python.runtime import platformType


dangerousPathError = error.NoResource("Invalid request URL.")

def isDangerous(path):
    return path == '..' or '/' in path or os.sep in path


class Data(resource.Resource):
    """
    This is a static, in-memory resource.
    """

    def __init__(self, data, type):
        resource.Resource.__init__(self)
        self.data = data
        self.type = type

    def render(self, request):
        request.setHeader("content-type", self.type)
        request.setHeader("content-length", str(len(self.data)))
        if request.method == "HEAD":
            return ''
        return self.data

def addSlash(request):
    qs = ''
    qindex = string.find(request.uri, '?')
    if qindex != -1:
        qs = request.uri[qindex:]
        
    return "http%s://%s%s/%s" % (
        request.isSecure() and 's' or '',
        request.getHeader("host"),
        (string.split(request.uri,'?')[0]),
        qs)

class Redirect(resource.Resource):
    def __init__(self, request):
        resource.Resource.__init__(self)
        self.url = addSlash(request)

    def render(self, request):
        return redirectTo(self.url, request)


class Registry(components.Componentized, styles.Versioned):
    """
    I am a Componentized object that will be made available to internal Twisted
    file-based dynamic web content such as .rpy and .epy scripts.
    """

    def __init__(self):
        components.Componentized.__init__(self)
        self._pathCache = {}

    persistenceVersion = 1

    def upgradeToVersion1(self):
        self._pathCache = {}

    def cachePath(self, path, rsrc):
        self._pathCache[path] = rsrc

    def getCachedPath(self, path):
        return self._pathCache.get(path)


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
            more = mimetypes.read_mime_types(location)
            if more is not None:
                contentTypes.update(more)
            
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

class File(resource.Resource, styles.Versioned, filepath.FilePath):
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

    @cvar childNotFound: L{Resource} used to render 404 Not Found error pages.
    """

    contentTypes = loadMimeTypes()

    contentEncodings = {
        ".gz" : "gzip",
        ".bz2": "bzip2"
        }

    processors = {}

    indexNames = ["index", "index.html", "index.htm", "index.trp", "index.rpy"]

    type = None

    ### Versioning

    persistenceVersion = 6

    def upgradeToVersion6(self):
        self.ignoredExts = []
        if self.allowExt:
            self.ignoreExt("*")
        del self.allowExt

    def upgradeToVersion5(self):
        if not isinstance(self.registry, Registry):
            self.registry = Registry()

    def upgradeToVersion4(self):
        if not hasattr(self, 'registry'):
            self.registry = {}

    def upgradeToVersion3(self):
        if not hasattr(self, 'allowExt'):
            self.allowExt = 0

    def upgradeToVersion2(self):
        self.defaultType = "text/html"

    def upgradeToVersion1(self):
        if hasattr(self, 'indexName'):
            self.indexNames = [self.indexName]
            del self.indexName

    def __init__(self, path, defaultType="text/html", ignoredExts=(), registry=None, allowExt=0):
        """Create a file with the given path.
        """
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, path)
        # Remove the dots from the path to split
        self.defaultType = defaultType
        if ignoredExts in (0, 1) or allowExt:
            warnings.warn("ignoredExts should receive a list, not a boolean")
            if ignoredExts or allowExt:
                self.ignoredExts = ['*']
            else:
                self.ignoredExts = []
        else:
            self.ignoredExts = list(ignoredExts)
        self.registry = registry or Registry()

    def ignoreExt(self, ext):
        """Ignore the given extension.

        Serve file.ext if file is requested
        """
        self.ignoredExts.append(ext)

    childNotFound = error.NoResource("File not found.")

    def directoryListing(self):
        from twisted.web.woven import dirlist
        return dirlist.DirectoryLister(self.path,
                                       self.listNames(),
                                       self.contentTypes,
                                       self.contentEncodings,
                                       self.defaultType)

    def getChild(self, path, request):
        """See twisted.web.Resource.getChild.
        """
        self.restat()
        
        if not self.isdir():
            return self.childNotFound

        if path:
            fpath = self.child(path)
        else:
            fpath = self.childSearchPreauth(*self.indexNames)
            if fpath is None:
                return self.directoryListing()

        if not fpath.exists():
            fpath = fpath.siblingExtensionSearch(*self.ignoredExts)
            if fpath is None:
                return self.childNotFound

        if platformType == "win32":
            # don't want .RPY to be different than .rpy, since that would allow
            # source disclosure.
            processor = InsensitiveDict(self.processors).get(fpath.splitext()[1])
        else:
            processor = self.processors.get(fpath.splitext()[1])
        if processor:
            return resource.IResource(processor(fpath.path, self.registry))
        return self.createSimilarFile(fpath.path)

    # methods to allow subclasses to e.g. decrypt files on the fly:
    def openForReading(self):
        """Open a file and return it."""
        return self.open()

    def getFileSize(self):
        """Return file size."""
        return self.getsize()


    def render(self, request):
        """You know what you doing."""
        self.restat()

        if self.type is None:
            self.type, self.encoding = getTypeAndEncoding(self.basename(),
                                                          self.contentTypes,
                                                          self.contentEncodings,
                                                          self.defaultType)

        if not self.exists():
            return self.childNotFound.render(request)

        if self.isdir():
            return self.redirect(request)

        #for content-length
        fsize = size = self.getFileSize()

#         request.setHeader('accept-ranges','bytes')

        if self.type:
            request.setHeader('content-type', self.type)
        if self.encoding:
            request.setHeader('content-encoding', self.encoding)

        try:
            f = self.openForReading()
        except IOError, e:
            import errno
            if e[0] == errno.EACCES:
                return error.ForbiddenResource().render(request)
            else:
                raise

        if request.setLastModified(self.getmtime()) is http.CACHED:
            return ''

# Commented out because it's totally broken. --jknight 11/29/04
#         try:
#             range = request.getHeader('range')
# 
#             if range is not None:
#                 # This is a request for partial data...
#                 bytesrange = string.split(range, '=')
#                 assert bytesrange[0] == 'bytes',\
#                        "Syntactically invalid http range header!"
#                 start, end = string.split(bytesrange[1],'-')
#                 if start:
#                     f.seek(int(start))
#                 if end:
#                     end = int(end)
#                     size = end
#                 else:
#                     end = size
#                 request.setResponseCode(http.PARTIAL_CONTENT)
#                 request.setHeader('content-range',"bytes %s-%s/%s " % (
#                     str(start), str(end), str(size)))
#                 #content-length should be the actual size of the stuff we're
#                 #sending, not the full size of the on-server entity.
#                 fsize = end - int(start)
# 
#             request.setHeader('content-length', str(fsize))
#         except:
#             traceback.print_exc(file=log.logfile)

        request.setHeader('content-length', str(fsize))
        if request.method == 'HEAD':
            return ''

        # return data
        FileTransfer(f, size, request)
        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET

    def redirect(self, request):
        return redirectTo(addSlash(request), request)

    def listNames(self):
        if not self.isdir():
            return []
        directory = self.listdir()
        directory.sort()
        return directory

    def listEntities(self):
        return map(lambda fileName, self=self: self.createSimilarFile(os.path.join(self.path, fileName)), self.listNames())

    def createPickleChild(self, name, child):
        if not os.path.isdir(self.path):
            resource.Resource.putChild(self, name, child)
        # xxx use a file-extension-to-save-function dictionary instead
        if type(child) == type(""):
            fl = open(os.path.join(self.path, name), 'wb')
            fl.write(child)
        else:
            if '.' not in name:
                name = name + '.trp'
            fl = open(os.path.join(self.path, name), 'wb')
            from pickle import Pickler
            pk = Pickler(fl)
            pk.dump(child)
        fl.close()

    def createSimilarFile(self, path):
        f = self.__class__(path, self.defaultType, self.ignoredExts, self.registry)
        # refactoring by steps, here - constructor should almost certainly take these
        f.processors = self.processors
        f.indexNames = self.indexNames[:]
        f.childNotFound = self.childNotFound
        return f

class FileTransfer(pb.Viewable):
    """
    A class to represent the transfer of a file over the network.
    """
    request = None

    def __init__(self, file, size, request):
        self.file = file
        self.size = size
        self.request = request
        self.written = self.file.tell()
        request.registerProducer(self, 0)

    def resumeProducing(self):
        if not self.request:
            return
        data = self.file.read(min(abstract.FileDescriptor.bufferSize, self.size - self.written))
        if data:
            self.written += len(data)
            # this .write will spin the reactor, calling .doWrite and then
            # .resumeProducing again, so be prepared for a re-entrant call
            self.request.write(data)
        if self.request and self.file.tell() == self.size:
            self.request.unregisterProducer()
            self.request.finish()
            self.request = None

    def pauseProducing(self):
        pass

    def stopProducing(self):
        self.file.close()
        self.request = None

    # Remotely relay producer interface.

    def view_resumeProducing(self, issuer):
        self.resumeProducing()

    def view_pauseProducing(self, issuer):
        self.pauseProducing()

    def view_stopProducing(self, issuer):
        self.stopProducing()


    synchronized = ['resumeProducing', 'stopProducing']

threadable.synchronize(FileTransfer)

"""I contain AsIsProcessor, which serves files 'As Is'
   Inspired by Apache's mod_asis
"""

class ASISProcessor(resource.Resource):

    def __init__(self, path, registry=None):
        resource.Resource.__init__(self)
        self.path = path
        self.registry = registry or Registry()

    def render(self, request):
        request.startedWriting = 1
        res = File(self.path, registry=self.registry)
        return res.render(request)
