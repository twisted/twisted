import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="pb",
        # metadata
        name="Twisted Perspective Broker",
        version="SVN-Trunk",
        description="Twisted Perspective Broker contains the native RPC protocol.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Brian Warner",
        maintainer_email="warner-newpb@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/newpb/",
        license="MIT",
        long_description="""\
Long description here.
""",
        )
