import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="xish",
        # metadata
        name="Twisted Xish",
        version="SVN-Trunk",
        description="Twisted Xish is some XML stuff.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Some dweeb",
        maintainer_email="???",
        url="http://twistedmatrix.com/projects/xish/",
        license="MIT",
        long_description="Twisted Xish is some XML stuff.",
        )
