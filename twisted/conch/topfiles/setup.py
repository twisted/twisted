import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="conch",
        scripts=dist.getScripts("conch"),
        # metadata
        name="Conch",
        version="SVN-Trunk",
        description="Conch is a SSHv2 implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Paul Swartz",
        maintainer_email="z3p@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/conch/",
        license="MIT",
        long_description="Conch is an SSHv2 implementation.  It includes a "
                        "server, client, a SFTP client, and a key generator."
    )
