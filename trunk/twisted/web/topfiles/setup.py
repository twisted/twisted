# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="web",
        scripts=dist.getScripts("web"),
        # metadata
        name="Twisted Web",
        description="Twisted web server, programmable in Python.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="James Knight",
        url="http://twistedmatrix.com/trac/wiki/TwistedWeb",
        license="MIT",
        long_description="""\
Twisted Web is a complete web server, aimed at hosting web
applications using Twisted and Python, but fully able to serve static
pages, also.
""",
        classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: No Input/Output (Daemon)",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python",
            "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
            "Topic :: Internet :: WWW/HTTP :: WSGI",
            "Topic :: Software Development :: Libraries :: Python Modules",
            ],
        )
