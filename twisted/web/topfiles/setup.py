import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="web",
        # metadata
        name="Twisted Web",
        version="0.1.0",
        description="Twisted Web is a web server.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="James Knight",
        maintainer_email="foom@fuhm.net",
        url="http://twistedmatrix.com/projects/web/",
        license="MIT",
        long_description="Twisted Web is a web server.",
        )
