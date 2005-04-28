import sys

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="conch",
        scripts=dist.getScripts("conch"),
        # metadata
        name="Conch",
        version="SVN-Trunk",
        description="Twisted SSHv2 implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Paul Swartz",
        maintainer_email="z3p@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/conch/",
        license="MIT",
        long_description="""\
Conch is an SSHv2 implementation using the Twisted framework.  It
includes a server, client, a SFTP client, and a key generator.
""",
    )
