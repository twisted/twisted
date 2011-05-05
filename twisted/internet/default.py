# -*- test-case-name: twisted.internet.test.test_default -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The most suitable default reactor for the current platform.

Depending on a specific application's needs, some other reactor may in
fact be better.
"""

__all__ = ["install"]

from twisted.python.runtime import platform


def _getInstallFunction(platform):
    """
    Return a function to install the reactor most suited for the given platform.

    @param platform: The platform for which to select a reactor.
    @type platform: L{twisted.python.runtime.Platform}

    @return: A zero-argument callable which will install the selected
        reactor.
    """
    # Linux: Once <http://twistedmatrix.com/trac/ticket/4429> is fixed
    # epoll should be the default.
    #
    # OS X: poll(2) is not exposed by Python because it doesn't
    # support all file descriptors (in particular, lack of PTY support
    # is a problem) -- see <http://bugs.python.org/issue5154>. kqueue
    # reactor is being rewritten (see
    # <http://twistedmatrix.com/trac/ticket/1918>), and also has same
    # restriction as poll(2) as far PTY support goes.
    #
    # Windows: IOCP should eventually be default, but still has a few
    # remaining bugs,
    # e.g. <http://twistedmatrix.com/trac/ticket/4667>.
    #
    # We therefore choose poll(2) on non-OS X POSIX platforms, and
    # select(2) everywhere else.
    if platform.getType() == 'posix' and not platform.isMacOSX():
        from twisted.internet.pollreactor import install
    else:
        from twisted.internet.selectreactor import install
    return install


install = _getInstallFunction(platform)
