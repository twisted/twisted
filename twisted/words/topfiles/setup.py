import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="words",
        # metadata
        name="Twisted Words",
        version="SVN-Trunk",
        description="Twisted Words is chat.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        maintainer_email="exarkun@divmod.com",
        url="http://twistedmatrix.com/projects/words/",
        license="MIT",
        long_description="Twisted Words is chat.",
        )
