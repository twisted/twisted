## WebDAV wraper for VFS using the akadav library

import string, time, urllib, urlparse, os
from twisted.protocols import http
from twisted.web import resource, server, error, static

from akadav import daverror, propfind, davutil

from twisted.vfs.ivfs import IFileSystemContainer, IFileSystemLeaf

class VFSDavProperty(propfind.DavProperty):

    def _do_resourcetype(self, name):
        try:
            if not self.resource.isLeaf and self.need_value:
                self._setResult(http.OK, "DAV:", name, "collection")
            else:
                self._setResult(http.OK, "DAV:", name)
        except OSError:
            if self.need_value:
                self._setResult(http.FORBIDDEN, "DAV:", name)
            else:
                pass

    def _do_getcontentlength(self, name):
        try:
            if not self.resource.isLeaf:
                if self.need_value:
                    self._setResult(http.NOT_FOUND, "DAV:", name)
                else:
                    pass
            else:
                if self.need_value:
                    size = str(self.resource.meta['size'] or 0)
                    self._setResult(http.OK, "DAV:", name, size)
                else:
                    self._setResult(http.OK, "DAV:", name)
        except OSError:
            if self.need_value:
                self._setResult(http.FORBIDDEN, "DAV:", name)
            else:
                pass

    def _do_getcontenttype(self, name):
        try:
            if not self.resource.isLeaf:
                if self.need_value:
                    self._setResult(
                        http.OK, "DAV:", name, "httpd/unix-directory")
                else:
                    self._setResult(http.OK, "DAV:", name)
            else:
                if self.need_value:
                    self._setResult(
                        http.OK, "DAV:", name, self.resource.contentType)
                else:
                    self._setResult(http.OK, "DAV:", name)
        except OSError:
            if self.need_value:
                self._setResult(http.FORBIDDEN, "DAV:", name)
            else:
                pass

class VFSPropFind(propfind.PropFind):
    """Subclassing the akadav PropFind to make it access VFS data."""

    def _getProps(self, doc, parent, resource, childname=""):
        # response element
        response = doc.createElement("a:response")
        parent.appendChild(response)
        # href element
        href = doc.createElement("a:href")
        response.appendChild(href)
        childname = urllib.quote(childname)

        href_text = doc.createTextNode(
            urlparse.urljoin(davutil.fixURLBase(self.uri), childname))
        href.appendChild(href_text)

        need_value = True
        if self.propname or self.allprop:
            self.props = propfind.validDAVProps
            if self.propname:
                need_value = False

        dprop = VFSDavProperty(resource, self.props, need_value)
        result = dprop.getResult()
        self._getNamedProperties(doc, response, result)
        if (self.depth != "0") and not resource.isLeaf:
            if self.depth == "1":
                self.depth = "0"
            for path, childVF in  resource.node.children():
                child = resource.getChild(path, self.request)
                childname = child.node.name or ""
                if not child.isLeaf:
                    childname = childname + "/"
                self._getProps(doc, parent, child, childname)


class TempResource(resource.Resource):

    def __init__(self, parent):
        print "SPAWNING A TEMP RESOURCE"
        resource.Resource.__init__(self)
        self.parent = parent

    def getChild(self, path, request):
        if not path or path == '.':
            return self
        if path == "..":
            return DavResource(self.node.parent)

    def render_GET(self, request):
        return error.NoResource("File not found.")

    def render_MKCOL(self, request):
        print "MKCOL"*10
        targetName = request.prepath[-1]

        #handling already existing resource
        if self.parent.node.exists(targetName):
            out = daverror.ConflictResource("Resource exists %s" %(request.uri,))
            return out.render(request)

        #if not self.isWritable():
        #    epage = daverror.ForbiddenResource(
        #        "creating %s forbidden" % request.uri)
        #    return epage.render(request)

        self.parent.node.createDirectory(targetName)
        out = daverror.CreatedResource("%s created" % request.uri)
        return out.render(request)

class MetaDataDict(dict):
    """A dict that returns an empty string for a nonexistant key."""
    def __getitem__(self, key):
        if not self.has_key(key):
            return ""
        return dict.__getitem__(self, key)

class DavResource(resource.Resource):
    """A Twisted.web.resource.Resource which can handle DAV requests, based
    directly on akadav DavRequest, but so many changes that subclassing would
    be pointless."""

    allowedMethods = ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS",
        "PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE")

    def __init__(self, node):
        resource.Resource.__init__(self)
        self.node = IFileSystemContainer(node, IFileSystemLeaf(node, None))
        self.isLeaf = False
        if IFileSystemLeaf.providedBy(self.node):
            self.isLeaf = True
        self.meta = MetaDataDict(self.node.getMetadata())
        self.contentType = self.meta['contentType'] or 'text/plain'
        self.contentEncoding = self.meta['contentEncoding']

    def getmtime(self):
        return self.meta['mtime'] or time.time()

    def getctime(self):
        return self.meta['ctime'] or time.time()


    def getChild(self, path, request):
        #This will never be called if isLeaf is True so..
        if not path or path == '.':
            return self
        if path == "..":
            return DavResource(self.node.parent)
        if self.node.exists(path):
            return DavResource(self.node.child(path))
        else:
            return TempResource(self)



    def render(self, request, dst=None):
        # for MS windows WebDAV client
        print ">"*20, request.method, "<"*20
        request.setHeader("ms-author-via", "DAV")
        m = getattr(self, "render_" + request.method, None)
        if not m:
            raise server.UnsupportedMethod(self.allowedMethods)
        return m(request)

    def render_GET(self, request):
        request.setHeader("content-type", self.contentType)
        request.setHeader("content-encoding", self.contentEncoding)

        request.setHeader('accept-ranges', 'bytes')
        # for MS windows WebDAV client
        request.setHeader('cache-control', 'no-cache')

        if request.method == "HEAD":
            return ""

        if False: #TODO check for permissions in ivfs??
            return error.ForbiddenResource().render(request)

        if request.setLastModified(self.getmtime()) is http.CACHED:
            return ""

        rangeHeader = request.getHeader("range")

        size = self.meta['size']
        if rangeHeader is not None:
            bytesRange = string.split(rangeHeader, '=')
            assert bytesRange[0] == "bytes", (
                "invalid http range header")
            start, end = string.split(bytesRange[1],'-')

            #TODO read partial data when ivfs can return it somehow..
            request.setResponseCode(http.PARTIAL_CONTENT)
            request.setHeader('content-range', 'bytes %s-%s/%s ' % (
                start, end, size))

            request.setHeader('content-length', size)


        import StringIO
        self.node.open(os.O_RDONLY)
        data = StringIO.StringIO( self.node.readChunk(0,10000))
        self.node.close()

        static.FileTransfer(data, size, request)
        return server.NOT_DONE_YET

    def render_OPTIONS(self, request):
        request.setHeader("content-length", 0)
        request.setHeader("DAV", "1")
        request.setHeader("Allow", string.join(list(self.allowedMethods), ", "))
        return ""

    def render_PROPFIND(self, request):

        pf = VFSPropFind(request)
        err_msg = pf.parse()

        if err_msg:
            epage = daverror.BadRequestResource(err_msg)
            return epage.render(request)

        request.setResponseCode(http.MULTI_STATUS)
        request.setHeader("cache-control", "no-cache")
        request.setHeader("content-type", 'text/xml; charset="utf-8"')
        body = pf.getResponse(self)
        return body


# STUFF FROM THE DavResource CLASS STILL TO BE PORTED:
#
#    def render_DELETE(self, request):
#        self.restat()
#        if not self.isRemovable():
#            epage = NoResource(
#                "deleting collection %s failed." % request.uri)
#            return epage.render(request)
#
#        if self.isdir():
#            depth = get_depth(request)
#            if not depth:
#                epage = BadRequestResource(
#                    "deleting collection %s failed."
#                    "because depth is not &quot;infinity&quot;"
#                    % request.uri)
#                return epage.render(request)
#
#            self.rmtree()
#        else:
#            self.remove()
#
#        epage = NoContentResource("%s deleted" % request.uri)
#        return epage.render(request)
#
#    def render_PUT(self, request):
#        self.restat()
#        if not self.isWritable():
#            epage = ForbiddenResource("putting %s failed" % request.uri)
#            return epage.render(request)
#
#        target_path = os.path.join(self.path, request.target_name)
#        child = self.getChild(request.target_name, request)
#        if isinstance(child, ErrorPage): # target does not exist
#            f = file(target_path, "wb")
#            data = request.content.read(abstract.FileDescriptor.bufferSize)
#            while data:
#                f.write(data)
#                data = request.content.read(abstract.FileDescriptor.bufferSize)
#            f.close()
#        else: # target exists
#            if child.isdir():
#                # Should I overwrite the existing collection ?
#                epage = ConflictResource("putting %s failed" % request.uri)
#                return epage.render(request)
#            else: # overwrite
#                fd, tmp_name = tempfile.mkstemp()
#                data = request.content.read(abstract.FileDescriptor.bufferSize)
#                while data:
#                    os.write(fd, data)
#                    data = request.content.read(
#                        abstract.FileDescriptor.bufferSize)
#                os.close(fd)
#                shutil.move(tmp_name, target_path)
#
#        epage = CreatedResource("%s created" % request.uri)
#        return epage.render(request)
#
#    def render_MOVE(self, request):
#        self.restat()
#        r = MOVEResource()
#        epage = r.preProcess(self, request)
#        if epage:
#            return epage.render(request)
#        epage = r.process(self, request)
#        return epage.render(request)
#
#    def render_COPY(self, request):
#        self.restat()
#        r = COPYResource()
#        epage = r.preProcess(self, request)
#        if epage:
#            return epage.render(request)
#        epage = r.process(self, request)
#        return epage.render(request)
