# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    extraMeta = dict(
        classifiers=[
            "Development Status :: 5 - Production/Stable",
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
Twisted Words contains implementations of many Instant Messaging protocols,
including IRC, Jabber, OSCAR (AIM & ICQ), and some functionality for creating
bots, inter-protocol gateways, and a client application for many of the
protocols.

In support of Jabber, Twisted Words also contains X-ish, a library for
processing XML with Twisted and Python, with support for a Pythonic DOM and
an XPath-like toolkit.
""",
        **extraMeta)
