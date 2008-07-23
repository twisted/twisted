# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Static resources for L{twisted.web}.
"""

import os
import warnings
import urllib
import itertools
import cgi

from twisted.web import server
from twisted.web import error
from twisted.web import resource
from twisted.web import http
from twisted.web.util import redirectTo

from twisted.python import components, filepath, log
from twisted.internet import abstract
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
    qindex = request.uri.find('?')
    if qindex != -1:
        qs = request.uri[qindex:]

    return "http%s://%s%s/%s" % (
        request.isSecure() and 's' or '',
        request.getHeader("host"),
        (request.uri.split('?')[0]),
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
        return DirectoryLister(self.path,
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


    def _parseRangeHeader(self, range):
        """
        Return a two-tuple of the start and stop value from the given range
        header.  Raise ValueError if the header is syntactically invalid or
        if the Bytes-Unit is anything other than "bytes".
        """
        try:
            kind, value = range.split('=', 1)
        except ValueError:
            raise ValueError("Missing '=' separator")
        kind = kind.strip()
        if kind != 'bytes':
            raise ValueError("Unsupported Bytes-Unit: %r" % (kind,))
        byteRanges = filter(None, map(str.strip, value.split(',')))
        if len(byteRanges) > 1:
            # Support for multiple ranges should be added later.  For now, this
            # implementation gives up.
            raise ValueError("Multiple Byte-Ranges not supported")
        firstRange = byteRanges[0]
        try:
            start, end = firstRange.split('-', 1)
        except ValueError:
            raise ValueError("Invalid Byte-Range: %r" % (firstRange,))
        if start:
            try:
                start = int(start)
            except ValueError:
                raise ValueError("Invalid Byte-Range: %r" % (firstRange,))
        else:
            start = None
        if end:
            try:
                end = int(end)
            except ValueError:
                raise ValueError("Invalid Byte-Range: %r" % (firstRange,))
        else:
            end = None
        if start is not None:
            if end is not None and start > end:
                # Start must be less than or equal to end or it is invalid.
                raise ValueError("Invalid Byte-Range: %r" % (firstRange,))
        elif end is None:
            # One or both of start and end must be specified.  Omitting both is
            # invalid.
            raise ValueError("Invalid Byte-Range: %r" % (firstRange,))
        return start, end



    def _doRangeRequest(self, request, (start, end)):
        """
        Responds to simple Range-Header requests. Simple means that only the
        first byte range is handled.

        @raise ValueError: If the given Byte-Ranges-Specifier was invalid

        @return: A three-tuple of the start, length, and end byte of the
            response.
        """
        size = self.getFileSize()
        if start is None:
            # Omitted start means that the end value is actually a start value
            # relative to the end of the resource.
            start = size - end
            end = size
        elif end is None:
            # Omitted end means the end of the resource should be the end of
            # the range.
            end = size
        elif end < size:
            # If the end was specified (this is an else for `end is None`) and
            # there's room, bump the value by one to compensate for the
            # disagreement between Python and the HTTP RFC on whether the
            # closing index of the range is inclusive (HTTP) or exclusive
            # (Python).
            end += 1
        if start >= size:
            # This range doesn't overlap with any of this resource, so the
            # request is unsatisfiable.
            request.setResponseCode(http.REQUESTED_RANGE_NOT_SATISFIABLE)
            request.setHeader(
                'content-range', 'bytes */%d' % (size,))
            start = end = 0
        else:
            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader(
                'content-range', 'bytes %d-%d/%d' % (start, end - 1, size))
        return start, (end - start), end


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

        request.setHeader('accept-ranges','bytes')

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

        # set the stop byte, and content-length
        contentLength = stop = self.getFileSize()

        byteRange = request.getHeader('range')
        if byteRange is not None:
            try:
                start, contentLength, stop = self._doRangeRequest(
                    request, self._parseRangeHeader(byteRange))
            except ValueError, e:
                log.msg("Ignoring malformed Range header %r" % (byteRange,))
                request.setResponseCode(http.OK)
            else:
                f.seek(start)

        request.setHeader('content-length', str(contentLength))
        if request.method == 'HEAD':
            return ''

        # return data
        FileTransfer(f, stop, request)
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



class ASISProcessor(resource.Resource):
    """
    Serve files exactly as responses without generating a status-line or any
    headers.  Inspired by Apache's mod_asis.
    """

    def __init__(self, path, registry=None):
        resource.Resource.__init__(self)
        self.path = path
        self.registry = registry or Registry()


    def render(self, request):
        request.startedWriting = 1
        res = File(self.path, registry=self.registry)
        return res.render(request)



def formatFileSize(size):
    """
    Format the given file size in bytes to human readable format.
    """
    if size < 1024:
        return '%iB' % size
    elif size < (1024 ** 2):
        return '%iK' % (size / 1024)
    elif size < (1024 ** 3):
        return '%iM' % (size / (1024 ** 2))
    else:
        return '%iG' % (size / (1024 ** 3))



class DirectoryLister(resource.Resource):
    """
    Print the content of a directory.

    @ivar template: page template used to render the content of the directory.
        It must contain the format keys B{header} and B{tableContent}.
    @type template: C{str}

    @ivar linePattern: template used to render one line in the listing table.
        It must contain the format keys B{class}, B{href}, B{text}, B{size},
        B{type} and B{encoding}.
    @type linePattern: C{str}

    @ivar contentEncodings: a mapping of extensions to encoding types.
    @type contentEncodings: C{dict}

    @ivar defaultType: default type used when no mimetype is detected.
    @type defaultType: C{str}

    @ivar dirs: filtered content of C{path}, if the whole content should not be
        displayed (default to C{None}, which means the actual content of
        C{path} is printed).
    @type dirs: C{NoneType} or C{list}

    @ivar path: directory which content should be listed.
    @type path: C{str}
    """

    template = """<html>
<head>
<title>%(header)s</title>
<style>
.even-dir { background-color: #efe0ef }
.even { background-color: #eee }
.odd-dir {background-color: #f0d0ef }
.odd { background-color: #dedede }
.icon { text-align: center }
.listing {
    margin-left: auto;
    margin-right: auto;
    width: 50%%;
    padding: 0.1em;
    }

body { border: 0; padding: 0; margin: 0; background-color: #efefef; }
h1 {padding: 0.1em; background-color: #777; color: white; border-bottom: thin white dashed;}

</style>
</head>

<body>
<h1>%(header)s</h1>

<table>
    <thead>
        <tr>
            <th>Filename</th>
            <th>Size</th>
            <th>Content type</th>
            <th>Content encoding</th>
        </tr>
    </thead>
    <tbody>
%(tableContent)s
    </tbody>
</table>

</body>
</html>
"""

    linePattern = """<tr class="%(class)s">
    <td><a href="%(href)s">%(text)s</a></td>
    <td>%(size)s</td>
    <td>%(type)s</td>
    <td>%(encoding)s</td>
</tr>
"""

    def __init__(self, pathname, dirs=None,
                 contentTypes=File.contentTypes,
                 contentEncodings=File.contentEncodings,
                 defaultType='text/html'):
        self.contentTypes = contentTypes
        self.contentEncodings = contentEncodings
        self.defaultType = defaultType
        # dirs allows usage of the File to specify what gets listed
        self.dirs = dirs
        self.path = pathname


    def _getFilesAndDirectories(self, directory):
        """
        Helper returning files and directories in given directory listing, with
        attributes to be used to build a table content with
        C{self.linePattern}.

        @return: tuple of (directories, files)
        @rtype: C{tuple} of C{list}
        """
        files = []
        dirs = []
        for path in directory:
            url = urllib.quote(path, "/")
            escapedPath = cgi.escape(path)
            if os.path.isdir(os.path.join(self.path, path)):
                url = url + '/'
                dirs.append({'text': escapedPath + "/", 'href': url,
                             'size': '', 'type': '[Directory]',
                             'encoding': ''})
            else:
                mimetype, encoding = getTypeAndEncoding(path, self.contentTypes,
                                                        self.contentEncodings,
                                                        self.defaultType)
                try:
                    size = os.stat(os.path.join(self.path, path)).st_size
                except OSError:
                    continue
                files.append({
                    'text': escapedPath, "href": url,
                    'type': '[%s]' % mimetype,
                    'encoding': (encoding and '[%s]' % encoding or ''),
                    'size': formatFileSize(size)})
        return dirs, files


    def _buildTableContent(self, elements):
        """
        Build a table content using C{self.linePattern} and giving elements odd
        and even classes.
        """
        tableContent = []
        rowClasses = itertools.cycle(['odd', 'even'])
        for element, rowClass in zip(elements, rowClasses):
            element["class"] = rowClass
            tableContent.append(self.linePattern % element)
        return tableContent


    def render(self, request):
        """
        Render a listing of the content of C{self.path}.
        """
        if self.dirs is None:
            directory = os.listdir(self.path)
            directory.sort()
        else:
            directory = self.dirs

        dirs, files = self._getFilesAndDirectories(directory)

        tableContent = "".join(self._buildTableContent(dirs + files))

        header = "Directory listing for %s" % (
            cgi.escape(urllib.unquote(request.uri)),)

        return self.template % {"header": header, "tableContent": tableContent}


    def __repr__(self):
        return '<DirectoryLister of %r>' % self.path

    __str__ = __repr__
