#!/usr/bin/env python

import os, os.path as osp, types
from os.path import join as opj

from twisted.python import components
import zope.interface as zi


class IFile(components.Interface):
   """an interface that models the stdlib's file object"""

   closed = zi.Attribute("bool indicating the current "
                                     "state of the file object")
   encoding = zi.Attribute("the encoding this file uses")
   mode = zi.Attribute("the I/O mode for this file")
   name = zi.Attribute("the name of the file"
                                   "(or appropriate alternative)") 
   newlines = zi.Attribute("keeps track of the types of "
                                       "newlines encountered in the file")
   softspace = zi.Attribute("Boolean that indicates whether"
                                        "a space character needs to be "
                                        "printed before another value "
                                        "when using the print statement")

   def close():
      """close the file"""

   def flush():
      """flush the internal buffer"""

   def next():
      """a file object's own iterator"""
   
   def read(size=-1):
      """read at most size bytes from the file"""

   # etc. etc. etc.
   
class File(object):
   zi.implements(IFile)

   closed = False
   encoding = "UTF-8"
   mode = "r"
   name = "bogus"
   newlines = '\n'
   softspace = False

   def close(self):
      pass

   def flush(self):
      pass

   def next(self):
      pass

   def read(self):
      pass


def main():
   name = IFile['name']
   read = IFile['read']
   iterLine = "repr('\\n\\t'.join([n for n in IFile])):\n%s" % '\n\t'.join([n for n in IFile])

   f = File()

   lines = ['\n',
            'IFile.__doc__: "%s"' % IFile.__doc__,
            'IFile.__name__: "%s"' % IFile.__name__,
            "\nuse mapping syntax to access an interfaces' attributes: \n",
            "name = IFile['name']",
            'type(name): %r' % type(name),
            'name.__name__: %r' % name.__name__,
            'name.__doc__: %r' % name.__doc__,
            '\n',
            "you can use 'in' to determine if an interface defines a name\n",
            "'name' in IFile: %r" % ('name' in IFile),
            "\n",
            "you can iterate over the names an interface provides\n",
            iterLine,
            "\n",
            "attributes that are methods provide access to the method signature\n",
            "read = IFile['read']",
            "read.getSignatureString(): %r\n" % read.getSignatureString(),
            "you can also inspect classes to see if they implement an interface",
            "IFile.implementedBy(File): %r\n" % IFile.implementedBy(File),
            "File doesn't *provide* IFile (as it is a class), it implements it",
            "IFile.providedBy(File): %r\n" % IFile.providedBy(File),
            "We can ask an object what interfaces it provides, however",
            "f = File()",
            "list(zope.interface.providedBy(f): %r" % list(zi.providedBy(f))
            ]

   print '\n'.join(lines)
   

if __name__ == '__main__':
    main()
