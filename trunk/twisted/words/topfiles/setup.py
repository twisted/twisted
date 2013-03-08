# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    if sys.version_info[:2] >= (2, 4):
        extraMeta = dict(
            classifiers=[
                "Development Status :: 4 - Beta",
                "Environment :: No Input/Output (Daemon)",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python",
                "Topic :: Communications :: Chat",
                "Topic :: Communications :: Chat :: AOL Instant Messenger",
                "Topic :: Communications :: Chat :: ICQ",
                "Topic :: Communications :: Chat :: Internet Relay Chat",
                "Topic :: Internet",
                "Topic :: Software Development :: Libraries :: Python Modules",
            ])
    else:
        extraMeta = {}

    dist.setup(
        twisted_subproject="words",
        scripts=dist.getScripts("words"),
        # metadata
        name="Twisted Words",
        description="Twisted Words contains Instant Messaging implementations.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        url="http://twistedmatrix.com/trac/wiki/TwistedWords",
        license="MIT",
        long_description="""\
Twisted Words contains implementations of many Instant Messaging
protocols, including IRC, Jabber, MSN, OSCAR (AIM & ICQ), TOC (AOL),
and some functionality for creating bots, inter-protocol gateways, and
a client application for many of the protocols.

In support of Jabber, Twisted Words also contains X-ish, a library for
processing XML with Twisted and Python, with support for a Pythonic DOM and
an XPath-like toolkit.
""",
        **extraMeta)
