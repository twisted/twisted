#!/usr/bin/env python

import os, os.path as osp, types
from os.path import join as opj

from twisted.python import components
import zope.interface 


class IFile(zope.interface.Interface):
   """an interface that models the stdlib's file object"""

   closed = zope.interface.Attribute("bool indicating the current "
                                     "state of the file object")
   encoding = zope.interface.Attribute("the encoding this file uses")
   mode = zope.interface.Attribute("the I/O mode for this file")
   name = zope.interface.Attribute("the name of the file"
                                   "(or appropriate alternative)") 
   newlines = zope.interface.Attribute("keeps track of the types of "
                                       "newlines encountered in the file")
   softspace = zope.interface.Attribute("Boolean that indicates whether"
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
   

def main():
   name = IFile['name']
   read = IFile['read']
   iterLine = "repr('\\n\\t'.join([n for n in IFile])):\n%s" % '\n\t'.join([n for n in IFile])

   lines = ['\n',
            'IFile.__doc__: "%s"' % IFile.__doc__,
            'IFile.__name__: "%s"' % IFile.__name__,
            "\nuse mapping syntax to access an interfaces' attributes: \n\n",
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
            "\n\n",
            "attributes that are methods provide access to the method signature\n",
            "read = IFile['read']",
            "read.getSignatureString(): %r" % read.getSignatureString()
            ])

   print '\n'.join(lines)
   

if __name__ == '__main__':
    main()
