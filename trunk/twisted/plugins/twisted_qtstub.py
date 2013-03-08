# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Backwards-compatibility plugin for the Qt reactor.

This provides a Qt reactor plugin named C{qt} which emits a deprecation
warning and a pointer to the separately distributed Qt reactor plugins.
"""

import warnings

from twisted.application.reactors import Reactor, NoSuchReactor

wikiURL = 'http://twistedmatrix.com/trac/wiki/QTReactor'
errorMessage = ('qtreactor is no longer a part of Twisted due to licensing '
                'issues. Please see %s for details.' % (wikiURL,))

class QTStub(Reactor):
    """
    Reactor plugin which emits a deprecation warning on the successful
    installation of its reactor or a pointer to further information if an
    ImportError occurs while attempting to install it.
    """
    def __init__(self):
        super(QTStub, self).__init__(
            'qt', 'qtreactor', 'QT integration reactor')


    def install(self):
        """
        Install the Qt reactor with a deprecation warning or try to point
        the user to further information if it cannot be installed.
        """
        try:
            super(QTStub, self).install()
        except (ValueError, ImportError):
            raise NoSuchReactor(errorMessage)
        else:
            warnings.warn(
                "Please use -r qt3 to import qtreactor",
                category=DeprecationWarning)


qt = QTStub()
