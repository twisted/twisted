# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
L{twisted.test.test_application.PluggableReactorTestCase.test_qtStub} uses
this helper program to test that when the QT reactor plugin is not
available, an attempt to select it via the deprecated name C{qt} fails
appropriately.

When installation fails, no output is produced.  When it succeeds, a message
is printed.
"""

import sys

from twisted.application import reactors


class QTNotImporter:
    """
    Import hook which unilaterally rejects any attempt to import
    C{qtreactor} so that we can reliably test the behavior of attempting to
    install it when it is not present.
    """
    def find_module(self, fullname, path):
        """
        Reject attempts to import C{qtreactor}.  Ignore everything else.
        """
        if fullname == 'qtreactor':
            raise ImportError('qtreactor does not exist!')



def main():
    """
    Try to install the reactor named C{qt}.  Expect it to not work.  Print
    diagnostics to stdout if something goes wrong, print nothing otherwise.
    """
    sys.meta_path.insert(0, QTNotImporter())
    try:
        reactors.installReactor('qt')
    except reactors.NoSuchReactor, e:
        if e.args != ('qt',):
            print 'Wrong arguments to NoSuchReactor:', e.args
        else:
            # Do nothing to indicate success.
            pass
    else:
        print 'installed qtreactor succesfully'
    sys.stdout.flush()

if __name__ == '__main__':
    main()
