import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject=sys.argv[0],
        # metadata
        name="Twisted Words",
        version="0.1.0",
        description="Twisted Words is chat.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        maintainer_email="exarkun@divmod.com",
        url="http://twistedmatrix.com/projects/words/",
        license="MIT",
        long_description="Twisted Words is chat.",
        )
