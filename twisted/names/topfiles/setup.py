import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="names",
        # metadata
        name="Twisted Names",
        version="SVN-Trunk",
        description="Twisted Names is a DNS implementation.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        maintainer_email="exarkun@divmod.com",
        url="http://twistedmatrix.com/projects/names/",
        license="MIT",
        long_description="Twisted Names is a DNS implementation.",
        )
