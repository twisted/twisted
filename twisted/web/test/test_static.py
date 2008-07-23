# -*- test-case-name: twisted.web.test.test_web -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.


import os

from twisted.trial.unittest import TestCase, FailTest
from twisted.web import static
from twisted.python.filepath import FilePath


class FakeRequest:
    method = 'GET'

    _headers = None
    _setHeaders = None
    _written = ''

    def __init__(self, uri=''):
        self._headers = {}
        self._setHeaders = {}
        self.uri = uri


    def getHeader(self, k):
        if self._headers is None:
            return None
        return self._headers.get(k)


    def setHeader(self, k, v):
        self._setHeaders.setdefault(k, []).append(v)


    def setLastModified(self, x):
        pass


    def registerProducer(self, producer, x):
        producer.resumeProducing()


    def unregisterProducer(self):
        pass


    def finish(self):
        pass


    def write(self, data):
        self._written = self._written + data



class Range(TestCase):
    todo = (FailTest, 'No range support yet.')

    def setUp(self):
        self.tmpdir = self.mktemp()
        os.mkdir(self.tmpdir)
        name = os.path.join(self.tmpdir, 'junk')
        f = file(name, 'w')
        f.write(8000 * 'x')
        f.close()
        self.file = static.File(name)
        self.request = FakeRequest()


    def testBodyLength(self):
        self.request._headers['range'] = 'bytes=0-1999'
        self.file.render(self.request)
        self.assertEquals(len(self.request._written), 2000)


    def testContentLength(self):
        """
        Content-Length of a request is correct.
        """
        self.request._headers['range'] = 'bytes=0-1999'
        self.file.render(self.request)
        self.assertEquals(self.request._setHeaders['content-length'], ['2000'])


    def testContentRange(self):
        """
        Content-Range of a request is correct.
        """
        self.request._headers['range'] = 'bytes=0-1999'
        self.file.render(self.request)
        self.assertEquals(self.request._setHeaders.get('content-range'), ['bytes 0-1999/8000'])



class DirectoryListerTest(TestCase):
    """
    Tests for L{static.DirectoryLister}.
    """

    def test_renderHeader(self):
        """
        L{static.DirectoryLister} prints the request uri as header of the
        rendered content.
        """
        path = FilePath(self.mktemp())
        path.makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(FakeRequest('foo'))
        self.assertIn("<h1>Directory listing for foo</h1>", data)
        self.assertIn("<title>Directory listing for foo</title>", data)


    def test_renderUnquoteHeader(self):
        """
        L{static.DirectoryLister} unquote the request uri before printing it.
        """
        path = FilePath(self.mktemp())
        path.makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(FakeRequest('foo%20bar'))
        self.assertIn("<h1>Directory listing for foo bar</h1>", data)
        self.assertIn("<title>Directory listing for foo bar</title>", data)


    def test_escapeHeader(self):
        """
        L{static.DirectoryLister} escape "&", "<" and ">" after unquoting the
        request uri.
        """
        path = FilePath(self.mktemp())
        path.makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(FakeRequest('foo%26bar'))
        self.assertIn("<h1>Directory listing for foo&amp;bar</h1>", data)
        self.assertIn("<title>Directory listing for foo&amp;bar</title>", data)


    def test_renderFiles(self):
        """
        L{static.DirectoryLister} is able to list all the files inside a
        directory.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('file1').setContent("content1")
        path.child('file2').setContent("content2" * 1000)

        lister = static.DirectoryLister(path.path)
        data = lister.render(FakeRequest('foo'))
        body = """<tr class="odd">
    <td><a href="file1">file1</a></td>
    <td>8B</td>
    <td>[text/html]</td>
    <td></td>
</tr>
<tr class="even">
    <td><a href="file2">file2</a></td>
    <td>7K</td>
    <td>[text/html]</td>
    <td></td>
</tr>"""
        self.assertIn(body, data)


    def test_renderDirectories(self):
        """
        L{static.DirectoryListerTest} is able to list all the directories
        inside a directory.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('dir1').makedirs()
        path.child('dir2 & 3').makedirs()

        lister = static.DirectoryLister(path.path)
        data = lister.render(FakeRequest('foo'))
        body = """<tr class="odd">
    <td><a href="dir1/">dir1/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>
<tr class="even">
    <td><a href="dir2%20%26%203/">dir2 &amp; 3/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>"""
        self.assertIn(body, data)


    def test_renderFiltered(self):
        """
        L{static.DirectoryListerTest} takes a optional C{dirs} argument that
        filter out the list of of directories and files printed.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('dir1').makedirs()
        path.child('dir2').makedirs()
        path.child('dir3').makedirs()
        lister = static.DirectoryLister(path.path, dirs=["dir1", "dir3"])
        data = lister.render(FakeRequest('foo'))
        body = """<tr class="odd">
    <td><a href="dir1/">dir1/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>
<tr class="even">
    <td><a href="dir3/">dir3/</a></td>
    <td></td>
    <td>[Directory]</td>
    <td></td>
</tr>"""
        self.assertIn(body, data)


    def test_oddAndEven(self):
        """
        L{static.DirectoryLister} gives an alternate class for each odd and
        even rows in the table.
        """
        lister = static.DirectoryLister(None)
        elements = [{"href": "", "text": "", "size": "", "type": "",
                     "encoding": ""}  for i in xrange(5)]
        content = lister._buildTableContent(elements)

        self.assertEquals(len(content), 5)
        self.assertTrue(content[0].startswith('<tr class="odd">'))
        self.assertTrue(content[1].startswith('<tr class="even">'))
        self.assertTrue(content[2].startswith('<tr class="odd">'))
        self.assertTrue(content[3].startswith('<tr class="even">'))
        self.assertTrue(content[4].startswith('<tr class="odd">'))


    def test_mimeTypeAndEncodings(self):
        """
        L{static.DirectoryLister} is able to detect mimetype and encoding of
        listed files.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        path.child('file1.txt').setContent("file1")
        path.child('file2.py').setContent("python")
        path.child('file3.conf.gz').setContent("conf compressed")
        path.child('file4.diff.bz2').setContent("diff compressed")
        directory = os.listdir(path.path)
        directory.sort()

        contentTypes = {
            ".txt": "text/plain",
            ".py": "text/python",
            ".conf": "text/configuration",
            ".diff": "text/diff"
        }

        lister = static.DirectoryLister(path.path, contentTypes=contentTypes)
        dirs, files = lister._getFilesAndDirectories(directory)
        self.assertEquals(dirs, [])
        self.assertEquals(files, [
            {'encoding': '',
             'href': 'file1.txt',
             'size': '5B',
             'text': 'file1.txt',
             'type': '[text/plain]'},
            {'encoding': '',
             'href': 'file2.py',
             'size': '6B',
             'text': 'file2.py',
             'type': '[text/python]'},
            {'encoding': '[gzip]',
             'href': 'file3.conf.gz',
             'size': '15B',
             'text': 'file3.conf.gz',
             'type': '[text/configuration]'},
            {'encoding': '[bzip2]',
             'href': 'file4.diff.bz2',
             'size': '15B',
             'text': 'file4.diff.bz2',
             'type': '[text/diff]'}])


    def test_brokenSymlink(self):
        """
        If on the file in the listing points to a broken symlink, it should not
        be returned by L{static.DirectoryLister._getFilesAndDirectories}.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        file1 = path.child('file1')
        file1.setContent("file1")
        file1.linkTo(path.child("file2"))
        file1.remove()

        lister = static.DirectoryLister(path.path)
        directory = os.listdir(path.path)
        directory.sort()
        dirs, files = lister._getFilesAndDirectories(directory)
        self.assertEquals(dirs, [])
        self.assertEquals(files, [])

    if getattr(os, "symlink", None) is None:
        test_brokenSymlink.skip = "No symlink support"


    def test_repr(self):
        """
        L{static.DirectoryListerTest.__repr__} gives the path of the lister.
        """
        path = FilePath(self.mktemp())
        lister = static.DirectoryLister(path.path)
        self.assertEquals(repr(lister),
                          "<DirectoryLister of %r>" % (path.path,))
        self.assertEquals(str(lister),
                          "<DirectoryLister of %r>" % (path.path,))

    def test_formatFileSize(self):
        """
        L{static.formatFileSize} format an amount of bytes into a more readable
        format.
        """
        self.assertEquals(static.formatFileSize(0), "0B")
        self.assertEquals(static.formatFileSize(123), "123B")
        self.assertEquals(static.formatFileSize(4567), "4K")
        self.assertEquals(static.formatFileSize(8900000), "8M")
        self.assertEquals(static.formatFileSize(1234000000), "1G")
        self.assertEquals(static.formatFileSize(1234567890000), "1149G")
