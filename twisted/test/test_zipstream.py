import random
import md5
import zipfile
import os.path
import shutil

from twisted.python import zipstream
from twisted.trial import unittest

# create some stuff that can be compressed
junk=' '.join([str(random.random()) for n in xrange(1000)])
junkmd5=md5.new(junk).hexdigest()

class ZipstreamTest(unittest.TestCase):
    """"""
    def test_unzipping(self):
        self.makeZipFiles()

        zipstream.unzip('littlefiles.zip')
        self.failUnless(os.path.isfile('zipstreamdir/937'))
        self.cleanupUnzippedJunk()

        uziter=zipstream.unzipIter('littlefiles.zip')
        r=uziter.next()
        self.assertEqual(r, 999)
        for r in uziter: pass
        self.assertEqual(r, 0)

        # test that files don't get overwritten unless you tell it to
        # do so
        # overwrite zipstreamjunk with some different contents
        stuff('zipstreamjunk', 'stuff')
        zipstream.unzip('bigfile.zip')
        newmd5=newsum('zipstreamjunk')
        self.assertEqual(newmd5, 'c13d88cb4cb02003daedb8a84e5d272a')

        zipstream.unzip('bigfile.zip', overwrite=1)
        newmd5=newsum('zipstreamjunk')
        self.assertEqual(newmd5, junkmd5)

        self.cleanupUnzippedJunk()

        uziter=zipstream.unzipIterChunky('bigfile.zip', chunksize=500)
        r=uziter.next()
        # test that the number of chunks is in the right ballpark;
        # this could theoretically be any number but statistically it
        # should always be in this range
        approx = 35<r<45
        self.failUnless(approx)
        for r in uziter: pass
        self.assertEqual(r, 0)
        newmd5=newsum('zipstreamjunk')
        self.assertEqual(newmd5, junkmd5)

        self.cleanupUnzippedJunk()

        uziter=zipstream.unzipIterChunky('bigfile_deflated.zip',
                                         chunksize=972)
        r=uziter.next()
        approx = 23<r<27
        self.failUnless(approx)
        for r in uziter: pass
        self.assertEqual(r, 0)
        newmd5=newsum('zipstreamjunk')
        self.assertEqual(newmd5, junkmd5)
        

    def _makebigfile(self, filename, compression):
        zf=zipfile.ZipFile(filename, 'w', compression)        
        for i in range(10):
            fn='zipstream%d' % i
            stuff(fn, '')
            zf.write(fn)
        stuff('zipstreamjunk', junk)
        zf.write('zipstreamjunk')
        zf.close()


    def makeZipFiles(self):
        self._makebigfile('bigfile.zip', zipfile.ZIP_STORED)

        zf2=zipfile.ZipFile('littlefiles.zip', 'w')
        try:
            os.mkdir('zipstreamdir')
        except EnvironmentError:
            pass
        for i in range(1000):
            fn='zipstreamdir/%d' % i
            stuff(fn, '')
            zf2.write(fn)
        zf2.close()

        self._makebigfile('bigfile_deflated.zip', zipfile.ZIP_DEFLATED)        

        self.cleanupUnzippedJunk()

    def cleanupUnzippedJunk(self):
        for i in range(10):
            rmDashRF('zipstream%d' % i)
        rmDashRF('zipstreamjunk')
        rmDashRF('zipstreamdir')

def rmDashRF(filename):
    if os.path.isfile(filename):
        os.remove(filename)
    elif os.path.isdir(filename):
        shutil.rmtree(filename, 1)
        
def stuff(filename, contents):
    """Create filename empty and put contents in it; return md5sum"""
    f=file(filename, 'w')
    f.write(contents)
    f.close()

def dump(filename):
    """Return contents of file as (string, md5) tuple"""
    f=file(filename, 'r')
    s=f.read()
    f.close()
    return s
        
def newsum(filename):
    """Return contents of file as md5 digest"""
    return md5.new(dump(filename)).hexdigest()
