import sys

from twisted.python import dist

if __name__ == '__main__':
    dist.setup(
        twisted_subproject="lore",
        scripts=dist.getScripts("lore"),
        # metadata
        name="Twisted Lore",
        version="SVN-Trunk",
        description="Twisted documentation system",
        author="Twisted Matrix Laboratories",
        author_email="twisted-python@twistedmatrix.com",
        maintainer="Andrew Bennetts",
        maintainer_email="spiv@twistedmatrix.com",
        url="http://twistedmatrix.com/projects/lore/",
        license="MIT",
        long_description="""\
Twisted Lore is a documentation generator with HTML and LaTeX support,
used in the Twisted project.
""",
        )
