import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject=sys.argv[0],
        # metadata
        name="Twisted Names",
        version="0.1.0",
        description="Twisted Names is a DNS implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        maintainer_email="exarkun@divmod.com",
        url="http://twistedmatrix.com/projects/names/",
        license="MIT",
        long_description="Twisted Names is a DNS implementation.",
        )
