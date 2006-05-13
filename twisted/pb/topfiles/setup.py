import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="pb",
        # metadata
        name="Twisted Perspective Broker, version 2",
        description="Twisted Perspective Broker contains the native RPC protocol.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Brian Warner",
        maintainer_email="warner-newpb@twistedmatrix.com",
        url="http://twistedmatrix.com/trac/wiki/NewPB",
        license="MIT",
        long_description="""\
pb2 (aka newpb) is a new version of Twisted's native RPC protocol, known as
'Perspective Broker'. This allows an object in one process to be used by code
in a distant process. This module provides data marshaling, a remote object
reference system, and a capability-based security model.
""",
        )
