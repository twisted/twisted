# -*- test-case-name: twisted.web.test.test_static -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Static resources for L{twisted.web}.
"""
from __future__ import annotations

import itertools
import mimetypes
import os
import warnings
from collections.abc import Callable, Sequence
from html import escape
from typing import IO, Any, Literal
from urllib.parse import quote, unquote

from incremental import Version

from twisted.python import components, filepath, log
from twisted.python.compat import nativeString, networkString
from twisted.python.deprecate import deprecated
from twisted.python.runtime import platformType
from twisted.python.url import URL
from twisted.python.util import InsensitiveDict
from twisted.web import http, resource, server
from twisted.web.util import redirectTo

# isort: off

# Disabling isort here because it mangles and reorders comments, and each of
# these imports has its own explanation.

# Incidentally re-exported because these were previously part of the public
# API.  Not mentioned in __all__, but not deprecated yet.
from ._ranges import (  # noqa:F401
    MultipleRangeStaticProducer,
    NoRangeStaticProducer,
    SingleRangeStaticProducer,
)

# This one is re-exported on purpose below, because it's part of a public type
# signature.
from ._ranges import StaticProducer

# This is our main *current* entry point into the _ranges module.
from ._ranges import _setupRangeProducer

# Called by request_HEAD to produce the same headers as request_GET.
from ._ranges import _simpleContentHeaders

# isort: on

__all__ = [
    "dangerousPathError",
    "isDangerous",
    "Data",
    "Redirect",
    "Registry",
    "loadMimeTypes",
    "File",
    # Intentionally exported because this is the type in a public interface.
    "StaticProducer",
]

dangerousPathError = resource._UnsafeNoResource("Invalid request URL.")


def isDangerous(path):
    return path == b".." or b"/" in path or networkString(os.sep) in path


class Data(resource.Resource):
    """
    This is a static, in-memory resource.
    """

    def __init__(self, data, type):
        """
        @param data: The bytes that make up this data resource.
        @type data: L{bytes}

        @param type: A native string giving the Internet media type for this
            content.
        @type type: L{str}
        """
        resource.Resource.__init__(self)
        self.data = data
        self.type = type

    def render_GET(self, request):
        request.setHeader(b"content-type", networkString(self.type))
        request.setHeader(b"content-length", b"%d" % (len(self.data),))
        if request.method == b"HEAD":
            return b""
        return self.data

    render_HEAD = render_GET


@deprecated(Version("Twisted", 16, 0, 0))
def addSlash(request):
    """
    Add a trailing slash to C{request}'s URI. Deprecated, do not use.
    """
    return _addSlash(request)


def _addSlash(request):
    """
    Add a trailing slash to C{request}'s URI.

    @param request: The incoming request to add the ending slash to.
    @type request: An object conforming to L{twisted.web.iweb.IRequest}

    @return: A URI with a trailing slash, with query and fragment preserved.
    @rtype: L{bytes}
    """
    url = URL.fromText(request.uri.decode("ascii"))
    # Add an empty path segment at the end, so that it adds a trailing slash
    url = url.replace(path=list(url.path) + [""])
    return url.asText().encode("ascii")


class Redirect(resource.Resource):
    def __init__(self, request):
        resource.Resource.__init__(self)
        self.url = _addSlash(request)

    def render(self, request):
        return redirectTo(self.url, request)


class Registry(components.Componentized):
    """
    I am a Componentized object that will be made available to internal Twisted
    file-based dynamic web content such as .rpy and .epy scripts.
    """

    def __init__(self):
        components.Componentized.__init__(self)
        self._pathCache = {}

    def cachePath(self, path, rsrc):
        self._pathCache[path] = rsrc

    def getCachedPath(self, path):
        return self._pathCache.get(path)


def loadMimeTypes(mimetype_locations=None, init=mimetypes.init):
    """
    Produces a mapping of extensions (with leading dot) to MIME types.

    It does this by calling the C{init} function of the L{mimetypes} module.
    This will have the side effect of modifying the global MIME types cache
    in that module.

    Multiple file locations containing mime-types can be passed as a list.
    The files will be sourced in that order, overriding mime-types from the
    files sourced beforehand, but only if a new entry explicitly overrides
    the current entry.

    @param mimetype_locations: Optional. List of paths to C{mime.types} style
        files that should be used.
    @type mimetype_locations: iterable of paths or L{None}
    @param init: The init function to call. Defaults to the global C{init}
        function of the C{mimetypes} module. For internal use (testing) only.
    @type init: callable
    """
    init(mimetype_locations)
    mimetypes.types_map.update(
        {
            ".conf": "text/plain",
            ".diff": "text/plain",
            ".flac": "audio/x-flac",
            ".java": "text/plain",
            ".oz": "text/x-oz",
            ".swf": "application/x-shockwave-flash",
            ".wml": "text/vnd.wap.wml",
            ".xul": "application/vnd.mozilla.xul+xml",
            ".patch": "text/plain",
        }
    )
    return mimetypes.types_map


def getTypeAndEncoding(filename, types, encodings, defaultType):
    p, ext = filepath.FilePath(filename).splitext()
    ext = filepath._coerceToFilesystemEncoding("", ext.lower())
    if ext in encodings:
        enc = encodings[ext]
        ext = os.path.splitext(p)[1].lower()
    else:
        enc = None
    type = types.get(ext, defaultType)
    return type, enc


class File(resource.Resource, filepath.FilePath[str]):
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
    @cvar forbidden: L{Resource} used to render 403 Forbidden error pages.

    @ivar contentTypes: a mapping of extensions to MIME types used to set the
        default value for the Content-Type header.
        It is initialized with the values returned by L{loadMimeTypes}.
    @type contentTypes: C{dict}

    @ivar contentEncodings: a mapping of extensions to encoding types used to
        set default value for the Content-Encoding header.
    @type contentEncodings: C{dict}
    """

    contentTypes = loadMimeTypes()

    contentEncodings = {".gz": "gzip", ".bz2": "bzip2"}

    processors: dict[str, Callable[[str, Any], Data]] = {}

    indexNames = ["index", "index.html", "index.htm", "index.rpy"]
    ignoredExts: Sequence[str]

    type: str | None
    type = None

    def __init__(
        self,
        path: str,
        defaultType: str = "text/html",
        ignoredExts: Sequence[str] = (),
        registry: Registry | None = None,
        allowExt: Literal[0] = 0,
    ) -> None:
        """
        Create a file with the given path.

        @param path: The filename of the file from which this L{File} will
            serve data.

        @param defaultType: A I{major/minor}-style MIME type specifier
            indicating the I{Content-Type} with which this L{File}'s data
            will be served if a MIME type cannot be determined based on
            C{path}'s extension.

        @param ignoredExts: A sequence giving the extensions of paths in the
            filesystem which will be ignored for the purposes of child
            lookup.  For example, if C{ignoredExts} is C{(".bar",)} and
            C{path} is a directory containing a file named C{"foo.bar"}, a
            request for the C{"foo"} child of this resource will succeed
            with a L{File} pointing to C{"foo.bar"}.

        @param registry: The registry object being used to handle this
            request.  If L{None}, one will be created.

        @param allowExt: Ignored parameter, only present for backwards
            compatibility.  Do not pass a value for this parameter.
        """
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, path)
        self.defaultType = defaultType
        if ignoredExts in (0, 1) or allowExt:
            warnings.warn(  # type:ignore[unreachable]
                "ignoredExts should receive a list, not a boolean"
            )
            if ignoredExts or allowExt:
                self.ignoredExts = ["*"]
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

    childNotFound = resource._UnsafeNoResource("File not found.")
    forbidden = resource._UnsafeForbiddenResource()

    def directoryListing(self):
        """
        Return a resource that generates an HTML listing of the
        directory this path represents.

        @return: A resource that renders the directory to HTML.
        @rtype: L{DirectoryLister}
        """
        path = self.path
        names = self.listNames()
        return DirectoryLister(
            path, names, self.contentTypes, self.contentEncodings, self.defaultType
        )

    def getChild(self, path, request):
        """
        If this L{File}"s path refers to a directory, return a L{File}
        referring to the file named C{path} in that directory.

        If C{path} is the empty string, return a L{DirectoryLister} instead.

        @param path: The current path segment.
        @type path: L{bytes}

        @param request: The incoming request.
        @type request: An that provides L{twisted.web.iweb.IRequest}.

        @return: A resource representing the requested file or directory, or a
            resource returning a NOT_FOUND error to clients if the path cannot
            be accessed.
        @rtype: An object that provides L{resource.IResource}.
        """
        if isinstance(path, bytes):
            try:
                # Request calls urllib.unquote on each path segment,
                # leaving us with raw bytes.
                path = path.decode("utf-8")
            except UnicodeDecodeError:
                log.err(None, f"Could not decode path segment as utf-8: {path!r}")
                return self.childNotFound

        self.restat(reraise=False)

        if not self.isdir():
            return self.childNotFound

        if path:
            try:
                fpath = self.child(path)
            except filepath.InsecurePath:
                return self.childNotFound
        else:
            fpath = self.childSearchPreauth(*self.indexNames)
            if fpath is None:
                return self.directoryListing()

        if not fpath.exists():
            fpath = fpath.siblingExtensionSearch(*self.ignoredExts)
            if fpath is None:
                return self.childNotFound

        extension = fpath.splitext()[1]
        if platformType == "win32":
            # don't want .RPY to be different than .rpy, since that would allow
            # source disclosure.
            processor = InsensitiveDict(self.processors).get(extension)
        else:
            processor = self.processors.get(extension)
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

    def makeProducer(
        self, request: http.Request, fileForReading: IO[bytes]
    ) -> StaticProducer:
        """
        Make a L{StaticProducer} that will produce the body of this response.

        This method will also set the response code and Content-* headers.

        @param request: The L{twisted.web.http.Request} object.

        @param fileForReading: The file object containing the resource.

        @return: A L{StaticProducer}.  Calling C{.start()} on this will begin
            producing the response.
        """
        return _setupRangeProducer(
            request,
            fileForReading,
            fileSize=self.getFileSize(),
            contentType=self.type,
            contentEncoding=self.encoding,
        )

    def _commonReadPreflight(self, request: http.Request) -> bytes | None:
        """
        Perform pre-flight checks common to C{GET} and C{HEAD} requests,
        executed before any file is opened for permission checks.

        @return: a 2-tuple of a boolean of "should we keep going" and what to
            return if we should not keep going.
        """
        self.restat(False)
        if self.type is None:
            self.type, self.encoding = getTypeAndEncoding(
                self.basename(),
                self.contentTypes,
                self.contentEncodings,
                self.defaultType,
            )
        if not self.exists():
            return self.childNotFound.render(request)
        if self.isdir():
            return self.redirect(request)
        if request.setLastModified(self.getModificationTime()) is http.CACHED:
            return b""
        request.setHeader(b"accept-ranges", b"bytes")
        return None

    def render_GET(self, request: http.Request) -> Any:
        """
        Begin sending the contents of this L{File} (or a subset of the
        contents, based on the 'range' header) to the given request.
        """
        if (earlyResult := self._commonReadPreflight(request)) is not None:
            return earlyResult
        try:
            fileForReading = self.openForReading()
        except PermissionError:
            return self.forbidden.render(request)
        try:
            producer = self.makeProducer(request, fileForReading)
            producer.start()
        except BaseException:
            fileForReading.close()
            raise
        return server.NOT_DONE_YET

    def render_HEAD(self, request: http.Request) -> Any:
        """
        Get the status of this file and return a HEAD response.
        """
        if self._commonReadPreflight(request) is not None:
            return b""
        try:
            with self.openForReading():
                pass
        except PermissionError:
            return self.forbidden.render(request)
        _simpleContentHeaders(request, self.getFileSize(), self.type, self.encoding)
        return b""

    def redirect(self, request: http.Request) -> bytes:
        return redirectTo(_addSlash(request), request)

    def listNames(self):
        if not self.isdir():
            return []
        directory = self.listdir()
        directory.sort()
        return directory

    def listEntities(self):
        return list(
            map(
                lambda fileName, self=self: self.createSimilarFile(
                    os.path.join(self.path, fileName)
                ),
                self.listNames(),
            )
        )

    def createSimilarFile(self, path):
        f = self.__class__(path, self.defaultType, self.ignoredExts, self.registry)
        # refactoring by steps, here - constructor should almost certainly take these
        f.processors = self.processors
        f.indexNames = self.indexNames[:]
        f.childNotFound = self.childNotFound
        return f


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
        return "%iB" % size
    elif size < (1024**2):
        return "%iK" % (size / 1024)
    elif size < (1024**3):
        return "%iM" % (size / (1024**2))
    else:
        return "%iG" % (size / (1024**3))


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

    @ivar contentTypes: a mapping of extensions to MIME types used to populate
        the information of a member of this directory.
        It is initialized with the value L{File.contentTypes}.
    @type contentTypes: C{dict}

    @ivar contentEncodings: a mapping of extensions to encoding types.
        It is initialized with the value L{File.contentEncodings}.
    @type contentEncodings: C{dict}

    @ivar defaultType: default type used when no mimetype is detected.
    @type defaultType: C{str}

    @ivar dirs: filtered content of C{path}, if the whole content should not be
        displayed (default to L{None}, which means the actual content of
        C{path} is printed).
    @type dirs: L{None} or C{list}

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

    def __init__(
        self,
        pathname,
        dirs=None,
        contentTypes=File.contentTypes,
        contentEncodings=File.contentEncodings,
        defaultType="text/html",
    ):
        resource.Resource.__init__(self)
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
            if isinstance(path, bytes):
                path = path.decode("utf8")

            url = quote(path, "/")
            escapedPath = escape(path)
            childPath = filepath.FilePath(self.path).child(path)

            if childPath.isdir():
                dirs.append(
                    {
                        "text": escapedPath + "/",
                        "href": url + "/",
                        "size": "",
                        "type": "[Directory]",
                        "encoding": "",
                    }
                )
            else:
                mimetype, encoding = getTypeAndEncoding(
                    path, self.contentTypes, self.contentEncodings, self.defaultType
                )
                try:
                    size = childPath.getsize()
                except OSError:
                    continue
                files.append(
                    {
                        "text": escapedPath,
                        "href": url,
                        "type": "[%s]" % mimetype,
                        "encoding": (encoding and "[%s]" % encoding or ""),
                        "size": formatFileSize(size),
                    }
                )
        return dirs, files

    def _buildTableContent(self, elements):
        """
        Build a table content using C{self.linePattern} and giving elements odd
        and even classes.
        """
        tableContent = []
        rowClasses = itertools.cycle(["odd", "even"])
        for element, rowClass in zip(elements, rowClasses):
            element["class"] = rowClass
            tableContent.append(self.linePattern % element)
        return tableContent

    def render(self, request):
        """
        Render a listing of the content of C{self.path}.
        """
        request.setHeader(b"content-type", b"text/html; charset=utf-8")
        if self.dirs is None:
            directory = os.listdir(self.path)
            directory.sort()
        else:
            directory = self.dirs

        dirs, files = self._getFilesAndDirectories(directory)

        tableContent = "".join(self._buildTableContent(dirs + files))

        header = "Directory listing for {}".format(
            escape(unquote(nativeString(request.uri))),
        )

        done = self.template % {"header": header, "tableContent": tableContent}
        done = done.encode("utf8")

        return done

    def __repr__(self) -> str:
        return "<DirectoryLister of %r>" % self.path

    __str__ = __repr__
