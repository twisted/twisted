import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="web2",
        # metadata
        name="Twisted Web2",
        version="SVN-Trunk",
        description="Twisted Web2 is a web server.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="James Knight",
        maintainer_email="foom@fuhm.net",
        url="http://twistedmatrix.com/projects/web/",
        license="MIT",
        long_description="Twisted Web2 is a web server.",
        )
