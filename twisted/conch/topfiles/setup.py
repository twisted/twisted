import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject=sys.argv[0],
        # metadata
        name="Twisted Conch",
        version="0.1.0",
        description="Twisted Conch is a ssh implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Paul Swartz",
        maintainer_email="z3p@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/conch/",
        license="MIT",
        long_description="Twisted conch is a ssh implementation.",
    )
