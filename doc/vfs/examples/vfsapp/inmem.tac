
import vfsapp

from twisted.vfs.backends import inmem

fdir = inmem.FakeDirectory()
fdir._children = {
    'abc': inmem.FakeFile( name='abc', parent=fdir, data="WOO WOO")
}

application = vfsapp.createVFSApplication(fdir)

