import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject=sys.argv[0],
        # metadata
        name="Twisted Mail",
        version="0.1.0",
        description="Twisted Mail is a mail server.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Jp Calderone",
        maintainer_email="exarkun@divmod.com",
        url="http://twistedmatrix.com/projects/mail/",
        license="MIT",
        long_description="Twisted Mail is a mail server.",
        )
