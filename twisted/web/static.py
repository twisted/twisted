
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

# Sibling Imports
import server
import error
import resource
import html
import widgets

# Twisted Imports
from twisted.protocols import http
from twisted.python import threadable, log
from twisted.internet import abstract
from twisted.spread import pb
from twisted.manhole import coil

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

class DirectoryListing(widgets.StreamWidget):
    def __init__(self, pathname):
        self.path = pathname

    def getTitle(self, request):
        return "Directory Listing For %s" % request.path

    def stream(self, write, request):
        write("<UL>\n")
        directory = os.listdir(self.path)
        directory.sort()
        for path in directory:
            write('<LI><A HREF="%s">%s</a>' % (path,path))
        write("</UL>\n")

class File(resource.Resource, coil.Configurable):
    """
    File is a resource that represents a plain non-interpreted file.
    It's constructor takes a file path.
    """
    contentTypes = {
        ".css": "text/css",
        ".exe": "application/x-executable",
        ".gif": "image/gif",
        ".gtar": "application/x-gtar",
        ".java": "text/plain",
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".lisp": "text/x-lisp",
        ".mp3":  "audio/mpeg",
        ".oz": "text/x-oz",
        ".pdf": "application/x-pdf",
        ".png": "image/png",
        ".py": "text/x-python",
        ".swf": "appplication/x-shockwave-flash",
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

    indexName = "index.html"

    ### Configuration

    configTypes = {'path': types.StringType,
                   'execCGI': 'boolean',
                   'execEPY': 'boolean'}

    configName = 'Web Filesystem Access'

    def config_path(self, path):
        self.path = path

    def config_execCGI(self, allowed):
        if allowed:
            import twcgi
            self.processors['.cgi'] = twcgi.CGIScript
        else:
            if self.processors.has_key('.cgi'):
                del self.processors['.cgi']

    def config_execEPY(self, allowed):
        if allowed:
            import script
            self.processors['.epy'] = script.PythonScript
        else:
            if self.processors.has_key('.epy'):
                del self.processors['.epy']


    def getConfiguration(self):
        return {'path': self.path,
                'execCGI': self.processors.has_key('.cgi'),
                'execEPY': self.processors.has_key('.epy')}

    def configInit(self, container, name):
        self.__init__("nowhere/nohow")

    ### End Configuration

    def __init__(self, path):
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
        self.type = self.contentTypes.get(string.lower(ext))
        self.processors = {}


    def getChild(self, path, request):
        """
        Move 'zig'. For great justice.
        """
        if path == '..':
            return error.NoResource()
        if path == '':
            path = self.indexName
            # This next step is so urls like
            #     /foo/bar/baz/
            # will be represented (internally) as
            #     ['foo','bar','baz','index.qux']
            # So that request.childLink() will work correctly.
            if os.path.exists(os.path.join(self.path,self.indexName)):
                request.prepath[-1] = self.indexName
            else:
                return widgets.WidgetPage(DirectoryListing(self.path))
        newpath = os.path.join(self.path, path)
        # forgive me, oh lord, for I know not what I do
        p, ext = os.path.splitext(newpath)
        processor = self.processors.get(ext)
        if processor:
            return processor(newpath)
        f = File(newpath)
        f.processors = self.processors
        f.indexName = self.indexName
        return f


    def render(self, request):
        "You know what you doing."
        try:
            mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime =\
                  os.stat(self.path)
        except OSError:
            return error.NoResource().render(request)
        if stat.S_ISDIR(mode):
            # tack a '/' on to the response if it's a directory.
            request.setHeader("location","http://%s%s/" % (
                request.getHeader("host"),
                (string.split(request.uri,'?')[0])))
            request.setResponseCode(http.MOVED_PERMANENTLY)
            return " "
        request.setHeader('accept-ranges','bytes')
        request.setHeader('last-modified', server.date_time_string(mtime))
        if self.type:
            request.setHeader('content-type', self.type)
        if self.encoding:
            request.setHeader('content-encoding', self.encoding)

        # caching headers support
        modified_since = request.getHeader('if-modified-since')
        if modified_since is not None:
            # check if file has been modified and if not don't return the file
            modified_since = server.string_date_time(modified_since)
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

coil.registerClass(File)

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
