"""I deal with static resources.
"""

# System Imports
import os, string, stat
import cStringIO
StringIO = cStringIO
del cStringIO

# Sibling Imports
import server
import error
import resource
import html

# Twisted Imports
from twisted.protocols import http
from twisted.python import threadable
from twisted.internet import abstract
from twisted.spread import pb

class Data(resource.Resource):
    """
    This is a static, in-memory resource.
    """

    def __init__(self, data, type):
        self.data = data
        self.type = type

    def render(self, request):
        request.setHeader("content-type", self.type)
        return self.data

class DirectoryListing(html.Interface):
    def __init__(self, pathname):
	html.Interface.__init__(self)
        self.path = pathname

    def directoryContents(self):
        io = StringIO.StringIO()
        io.write("<UL>\n")
        for path in os.listdir(self.path):
            io.write('<LI><A HREF="%s">%s</a>' % (path,path))
        io.write("</UL>\n")
        return io.getvalue()

    def pagetitle(self, request):
        return "Directory Listing For %s" % request.path[:-len('.idx')]
    def content(self, request):
        return "<CENTER>"+self.runBox(request, "Directory Contents",
                                      self.directoryContents)+"</CENTER>"


class File(resource.Resource):
    """
    File is a resource that represents a plain non-interpreted file.
    It's constructor takes a file path.
    """
    contentTypes = {
        ".png": "image/png",
        ".gif": "image/gif",
        ".txt": "text/plain",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".mp3":  "audio/mpeg",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".swf": "appplication/x-shockwave-flash",
        ".tar": "application/x-tar",
        ".tgz": "application/x-gtar",
        ".gtar": "application/x-gtar",
        ".zip": "application/x-zip",
        ".py": "text/x-python",
        ".lisp": "text/x-lisp",
        ".oz": "text/x-oz",
        ".java": "text/plain",
        ".pdf": "application/x-pdf",
	".exe": "application/x-executable",
        }

    contentEncodings = {
        ".gz" : "application/x-gzip",
        ".bz2": "appliation/x-bzip2"
        }

    processors = {}

    indexName = "index.html"

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


    def getChild(self, path, request):
        """
        Move 'zig'. For great justice.
        """
        if path == '..':
            return error.NoResource()
        if path == '.idx':
            if os.path.exists(os.path.join(self.path,self.indexName)):
                return error.NoResource()
            else:
                return DirectoryListing(self.path)
        if path == '':
            path = self.indexName
            # This next step is so urls like
            #     /foo/bar/baz/
            # will be represented (internally) as
            #     ['foo','bar','baz','index.qux']
            # So that request.childLink() will work correctly.
            request.prepath[-1] = self.indexName
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
            # This part is quite hacky, but it gets the job done.  What I'm
            # saying here is to redirect to .idx (the directory index) if this
            # is supposed to be an index.html but no index.html actually
            # exists.
            if os.path.basename(self.path) == self.indexName:
                request.setResponseCode(http.MOVED_PERMANENTLY)
                request.setHeader("location","http://%s%s.idx" % (
                    request.getHeader("host"),
                    (string.split(request.uri,'?')[0])))
                return ' '
            return error.NoResource().render(request)
        if stat.S_ISDIR(mode):
            # tack a '/' on to the response -- this isn't exactly correct, but
            # works for the avg. case now.  If you're looking for an index
            # which doesn't exist, tack on a "/.idx" instead, which will cause
            # the directory index to be loaded.
            if os.path.exists(os.path.join(self.path,self.indexName)):
                loc = ''
            else:
                loc = '.idx'
            request.setHeader("location","http://%s%s/%s" % (
                request.getHeader("host"),
                (string.split(request.uri,'?')[0]),
                loc))
            request.setResponseCode(http.MOVED_PERMANENTLY)
            return " "
        request.setHeader('accept-ranges','bytes')
        request.setHeader('last-modified', server.date_time_string(mtime))
        if self.type:
            request.setHeader('content-type', self.type)
        if self.encoding:
            request.setHeader('content-encoding', self.encoding)

        f = open(self.path)
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

        # return data
        FileTransfer(f, size, request)
        # and make sure the connection doesn't get closed
        return server.NOT_DONE_YET


class FileTransfer(pb.Proxied):
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

    def proxy_resumeProducing(self, issuer):
        self.resumeProducing()

    def proxy_pauseProducing(self, issuer):
        self.pauseProducing()

    def proxy_stopProducing(self, issuer):
        self.stopProducing()
    

    synchronized = ['resumeProducing', 'stopProducing']

threadable.synchronize(FileTransfer)
