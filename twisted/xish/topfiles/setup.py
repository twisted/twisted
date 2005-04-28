import sys

try:
    from twisted.python import dist
except ImportError:
    raise SystemExit("twisted.python.dist module not found.  Make sure you "
                     "have installed the Twisted core package before "
                     "attempting to install any other Twisted projects.")

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="xish",
        # metadata
        name="Twisted Xish",
        version="SVN-Trunk",
        description="Twisted Xish is an XML library with XPath-ish and DOM-ish support.",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Ralph Meijer",
        maintainer_email="twisted@ralphm.ik.nu",
        url="http://twistedmatrix.com/projects/xish/",
        license="MIT",
        long_description="""\
Twisted X-ish is a library for processing XML with Twisted and Python,
with support for a Pythonic DOM and an XPath-like toolkit. It exists
largely to facilitate the Jabber support in Twisted Words.
""",
        )
