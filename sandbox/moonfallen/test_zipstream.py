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
        for r in uziter:
            pass
        self.assertEqual(r, 0)

        uziter=zipstream.unzipIter('bigfile.zip')
        r=uziter.next()
        self.assertEqual(r, 10)
        for r in uziter:
            pass
        self.assertEqual(r, 0)
        junkstat=os.stat('zipstreamjunk')
        f=file('zipstreamjunk')
        data=f.read()
        f.close()
        newmd5=md5.new(data).hexdigest()
        self.assertEqual(newmd5, junkmd5)

        # test that files don't get overwritten unless you tell it to
        # do so
        zipstream.unzip('bigfile.zip')
        f=file('zipstreamjunk')
        data=f.read()
        f.close()
        newmd5=md5.new(data).hexdigest()
        newstat=os.stat('zipstreamjunk')
        self.assertEqual(newmd5, junkmd5)
        self.assertEqual(junkstat, newstat)

        zipstream.unzip('bigfile.zip', overwrite=1)
        f=file('zipstreamjunk')
        data=f.read()
        f.close()
        newmd5=md5.new(data).hexdigest()
        newstat=os.stat('zipstreamjunk')
        self.assertEqual(newmd5, junkmd5)

        self.cleanupUnzippedJunk()

        uziter=zipstream.unzipIterChunky('bigfile.zip', chunksize=500)
        r=uziter.next()
        approx=35<r<45
        self.failUnless(approx)
        for r in uziter:
            pass
        f=file('zipstreamjunk')
        data=f.read()
        f.close()
        newmd5=md5.new(data).hexdigest()
        self.assertEqual(newmd5, junkmd5)

    test_unzipping.todo="test bigfile_deflated"

    def _makebigfile(self, filename, compression):
        zf=zipfile.ZipFile(filename, 'w', compression)        
        for i in range(10):
            f=file('zipstream%d' % i, 'w')
            f.close()
            zf.write('zipstream%d' % i)
        fjunk=file('zipstreamjunk', 'w')
        fjunk.write(junk)
        fjunk.close()
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
            f=file('zipstreamdir/%d' % i, 'w')
            f.close()
            zf2.write('zipstreamdir/%d' % i)
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
        
