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
            "Topic :: Internet :: Name Service (DNS)",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ])

    dist.setup(
        twisted_subproject="names",
        # metadata
        name="Twisted Names",
        description="A Twisted DNS implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        url="http://twistedmatrix.com/trac/wiki/TwistedNames",
        license="MIT",
        long_description="""\
Twisted Names is both a domain name server as well as a client
resolver library. Twisted Names comes with an "out of the box"
nameserver which can read most BIND-syntax zone files as well as a
simple Python-based configuration format. Twisted Names can act as an
authoritative server, perform zone transfers from a master to act as a
secondary, act as a caching nameserver, or any combination of
these. Twisted Names' client resolver library provides functions to
query for all commonly used record types as well as a replacement for
the blocking gethostbyname() function provided by the Python stdlib
socket module.
""",
        **extraMeta)
