import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject=sys.argv[0],
        # metadata
        name="Twisted Pair",
        version="0.1.0",
        description="Twisted Pair is low-level netorking stuff.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Tommi Virtanen",
        maintainer_email="tv@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/pair/",
        license="MIT",
        long_description="Twisted Pair is low-level netorking stuff.",
        )
