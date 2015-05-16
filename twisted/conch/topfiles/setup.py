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
            "Environment :: Console",
            "Environment :: No Input/Output (Daemon)",
            "Intended Audience :: Developers",
            "Intended Audience :: End Users/Desktop",
            "Intended Audience :: System Administrators",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python",
            "Topic :: Internet",
            "Topic :: Security",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Terminals",
        ])

    dist.setup(
        twisted_subproject="conch",
        scripts=dist.getScripts("conch"),
        # metadata
        name="Twisted Conch",
        description="Twisted SSHv2 implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Paul Swartz",
        url="http://twistedmatrix.com/trac/wiki/TwistedConch",
        license="MIT",
        long_description="""\
Conch is an SSHv2 implementation using the Twisted framework.  It
includes a server, client, a SFTP client, and a key generator.
""",
        **extraMeta)
