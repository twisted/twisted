
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""I deal with static resources.
"""


# System Imports
import os, string, stat
import cStringIO
import traceback
import types
StringIO = cStringIO
del cStringIO
import urllib

# Sibling Imports
import server
import error
import resource
import html
import widgets

# Twisted Imports
from twisted.protocols import http
from twisted.python import threadable, log, components
from twisted.internet import abstract
from twisted.spread import pb
from twisted.persisted import styles

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
        if request.method == "HEAD":
            request.setHeader("content-length", len(self.data))
            return ''
        return self.data

class Redirect(resource.Resource):
    def __init__(self, url):
        self.url = url
    
    def render(self, request):
        request.setHeader("location", self.url)
        request.setResponseCode(http.TEMPORARY_REDIRECT)
        return """
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=%(url)s\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <!- The user\'s browser must be incredibly feeble if they have to click...-->
        Click <a href=\"%(url)s\">here</a>.
    </body>
</html>
""" % {'url': self.url}

class File(resource.Resource, styles.Versioned):
    """
    File is a resource that represents a plain non-interpreted file.
    It's constructor takes a file path.
    """
    
    # we don't implement IConfigCollection
    __implements__ = resource.IResource
    
    contentTypes = {
        ".css": "text/css",
        ".exe": "application/x-executable",
        ".gif": "image/gif",
        ".gtar": "application/x-gtar",
        ".html": "text/html",
        ".htm": "text/html",
        ".java": "text/plain",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".lisp": "text/x-lisp",
        ".mp3":  "audio/mpeg",
        ".oz": "text/x-oz",
        ".pdf": "application/x-pdf",
        ".png": "image/png",
        ".py": "text/x-python",
        ".swf": "application/x-shockwave-flash",
        ".tar": "application/x-tar",
        ".tgz": "application/x-gtar",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".txt": "text/plain",
        ".zip": "application/x-zip",
        }

    contentEncodings = {
        ".gz" : "application/x-gzip",
        ".bz2": "appliation/x-bzip2"
        }

    processors = {}

    indexNames = ["index", "index.html", "index.trp"]

    ### Versioning

    persistenceVersion = 3

    def upgradeToVersion3(self):
        if not hasattr(self, 'allowExt'):
            self.allowExt = 0

    def upgradeToVersion2(self):
        self.defaultType = "text/html"

    def upgradeToVersion1(self):
        if hasattr(self, 'indexName'):
            self.indexNames = [self.indexName]
            del self.indexName

    def __init__(self, path, defaultType="text/html", allowExt=0):
        """Create a file with the given path.
        """
        resource.Resource.__init__(self)
        self.path = path
        # Remove the dots from the path to split
        p = os.path.abspath(path)
        p, ext = os.path.splitext(p)
        self.encoding = self.contentEncodings.get(string.lower(ext))
        # if there was an encoding, get the next suffix
        if self.encoding is not None:
            p, ext = os.path.splitext(p)
        self.defaultType = defaultType
        self.allowExt = allowExt
        self.type = self.contentTypes.get(string.lower(ext), defaultType)

    def getChild(self, path, request):
        """See twisted.web.Resource.getChild.
        """
        if path == '..':
            return error.NoResource("Invalid request URL.")

        childPath = os.path.join(self.path, path)
        try:
            mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime =\
                  os.stat(childPath)
        except OSError:
            mode=0

        if os.path.isdir(childPath): # 'stat.S_ISDIR(mode)' is faster but doesn't work on jython
            # If someone is looking for children with a PathReferenceContext,
            # the request won't have a prepath, and we shouldn't do this kind
            # of mangling anyway because it has already been done.
            if hasattr(request, 'postpath') and not request.postpath and request.uri[-1] != '/':
                return self.redirect(request)
            if os.path.exists(childPath):
                if hasattr(request, 'postpath') and not request.postpath and not self.getIndex(request):
                    return widgets.WidgetPage(DirectoryListing(self.path))

        ##
        # If we're told to, allow requests for 'foo' to return
        # 'foo.bar'.
        ##
        if not os.path.exists(childPath):
            if self.allowExt and path and os.path.isdir(self.path):
                for fn in os.listdir(self.path):
                    if os.path.splitext(fn)[0]==path:
                        log.msg('    Returning %s' % fn)
                        newpath = os.path.join(self.path, fn)
                childPath = os.path.join(self.path, path)

        if not os.path.exists(childPath):
            # Before failing ask index.foo if it knows about this child
            index = self.getIndex(request)
            if index:
                child = index.getChild(path, request)
                if child:
                    return child
            return error.NoResource("File not found.")

        # forgive me, oh lord, for I know not what I do
        p, ext = os.path.splitext(childPath)
        processor = self.processors.get(ext)
        if processor:
            p = processor(childPath)
            if components.implements(p, resource.IResource):
                return p
            else:
                adapter = components.getAdapter(p, resource.IResource, None)
                if not adapter:
                    raise "%s instance does not implement IResource, and there is no registered adapter." % p.__class__
                return adapter

        f = File(childPath, self.defaultType, self.allowExt)
        f.processors = self.processors
        f.indexNames = self.indexNames[:]
        
        return f

    def render(self, request):
        "You know what you doing."
        mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime =\
              os.stat(self.path)

        if os.path.isdir(self.path): # stat.S_ISDIR(mode) (see above)
            index = self.getIndex(request)
            if index:
                return index.render(request)
    
            dirListingPage = WidgetPage(DirectoryListing(self.path))
            return dirListingPage.render(request)

        request.setHeader('accept-ranges','bytes')
        request.setHeader('last-modified', http.datetimeToString(mtime))
        if self.type:
            request.setHeader('content-type', self.type)
        if self.encoding:
            request.setHeader('content-encoding', self.encoding)

        # caching headers support
        modified_since = request.getHeader('if-modified-since')
        if modified_since is not None:
            # check if file has been modified and if not don't return the file
            modified_since = http.stringToDatetime(modified_since)
            if modified_since >= mtime:
                request.setResponseCode(http.NOT_MODIFIED)
                return ''

        f = open(self.path,'rb')
        try:
            range = request.getHeader('range')
            if range is not None:
                # This is a request for partial data...
                bytesrange = string.split(range, '=')
                assert bytesrange[0] == 'bytes',\
                       "Syntactically invalid http range header!"
                start, end = string.split(bytesrange[1],'-')
                if start:
                    f.seek(int(start))
                if end:
                    end = int(end)
                    size = end
                else:
                    end = size
                request.setResponseCode(http.PARTIAL_CONTENT)
                request.setHeader('content-range',"bytes %s-%s/%s " % (
                    str(start), str(end), str(size)))
            else:
                request.setHeader('content-length',size)
        except:
            traceback.print_exc(file=log.logfile)

        if request.method == 'HEAD':
            return ''

        # return data
        FileTransfer(f, size, request)
        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET

    def redirect(self, request):
        redirectURL = "http://%s%s/" % (
            request.getHeader("host"),
            (string.split(request.uri,'?')[0]))
        return Redirect(redirectURL)

    def getIndex(self, request):
        if not hasattr(request, 'prepath'): return
        for name in self.indexNames:
            ##
            # This next step is so urls like
            #     /foo/bar/baz/
            # will be represented (internally) as
            #     ['foo','bar','baz','index.qux']
            # So that request.childLink() will work correctly.
            ##
            if os.path.exists(os.path.join(self.path, name)):
                request.prepath[-1] = name
                request.acqpath[-1] = name
                return self.getChild(name, request)

    def listNames(self):
        if not os.path.isdir(self.path): return []
        directory = os.listdir(self.path)
        directory.sort()
        return directory
    
    def listEntities(self):
        return map(lambda fileName, self=self: File(os.path.join(self.path, fileName)), self.listNames())

    def putChild(self, name, child):
        if not os.path.isdir(self.path):
            resource.Resource.putChild(self, name, child)
        # xxx use a file-extension-to-save-function dictionary instead
        if type(child) == type(""):
            fl = open(os.path.join(self.path, name), 'w')
            fl.write(child)
        else:
            if '.' not in name:
                name += '.trp'
            fl = open(os.path.join(self.path, name), 'w')
            from pickle import Pickler
            pk = Pickler(fl)
            pk.dump(child)
        fl.close()

class DirectoryListing(File, widgets.StreamWidget):
    def __init__(self, pathname):
        self.path = pathname

    def getTitle(self, request):
        return "Directory Listing For %s" % request.path

    def stream(self, write, request):
        write("<UL>\n")
        directory = os.listdir(self.path)
        directory.sort()
        for path in directory:
            write('<LI><A HREF="%s">%s</a>' % (urllib.quote(path, "/:"), path))
        write("</UL>\n")

class FileTransfer(pb.Viewable):
    """
    A class to represent the transfer of a file over the network.
    """
    request = None
    def __init__(self, file, size, request):
        self.file = file
        self.size = size
        self.request = request
        request.registerProducer(self, 0)

    def resumeProducing(self):
        if not self.request:
            return
        self.request.write(self.file.read(abstract.FileDescriptor.bufferSize))
        if self.file.tell() == self.size:
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
