import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="news",
        # metadata
        name="Twisted News",
        version="SVN-Trunk",
        description="Twisted News is a news server.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        maintainer_email="exarkun@divmod.com",
        url="http://twistedmatrix.com/projects/news/",
        license="MIT",
        long_description="Twisted News is a news server.",
    )

