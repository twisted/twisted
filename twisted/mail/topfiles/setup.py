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
            "Topic :: Communications :: Email :: Post-Office :: IMAP",
            "Topic :: Communications :: Email :: Post-Office :: POP3",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ])

    dist.setup(
        twisted_subproject="mail",
        scripts=dist.getScripts("mail"),
        # metadata
        name="Twisted Mail",
        description="A Twisted Mail library, server and client.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        url="http://twistedmatrix.com/trac/wiki/TwistedMail",
        license="MIT",
        long_description="""\
An SMTP, IMAP and POP protocol implementation together with clients
and servers.

Twisted Mail contains high-level, efficient protocol implementations
for both clients and servers of SMTP, POP3, and IMAP4. Additionally,
it contains an "out of the box" combination SMTP/POP3 virtual-hosting
mail server. Also included is a read/write Maildir implementation and
a basic Mail Exchange calculator.
""",
        **extraMeta)
