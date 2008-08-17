# You can run this .tac file directly with:
#    twistd -ny adhoc.tac

import vfsapp

from twisted.vfs.backends import inmem, osfs, adhoc

root = adhoc.AdhocDirectory()

real = osfs.OSDirectory('.', name='real')

fake = inmem.FakeDirectory(name='fake')
fake.createFile('abc').writeChunk(0, 'WOO HOO')

root.putChild('real', real)
root.putChild('fake', fake)

application = vfsapp.createVFSApplication(root)

