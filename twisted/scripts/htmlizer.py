# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""HTML pretty-printing for Python source code."""

__version__ = '$Revision: 1.8 $'[11:-2]

from twisted.python import htmlizer, usage
from twisted import copyright

import os, sys

header = '''<html><head>
<title>%(title)s</title>
<meta name=\"Generator\" content="%(generator)s" />
%(alternate)s
%(stylesheet)s
</head>
<body>
'''
footer = """</body>"""

styleLink = '<link rel="stylesheet" href="%s" type="text/css" />'
alternateLink = '<link rel="alternate" href="%(source)s" type="text/x-python" />'

class Options(usage.Options):
    synopsis = """%s [options] source.py
    """ % (
        os.path.basename(sys.argv[0]),)

    optParameters = [
        ('stylesheet', 's', None, "URL of stylesheet to link to."),
        ]

    def parseArgs(self, filename):
        self['filename'] = filename

def run():
    options = Options()
    try:
        options.parseOptions()
    except usage.UsageError, e:
        print str(e)
        sys.exit(1)
    filename = options['filename']
    if options.get('stylesheet') is not None:
        stylesheet = styleLink % (options['stylesheet'],)
    else:
        stylesheet = ''

    output = open(filename + '.html', 'w')
    try:
        output.write(header % {
            'title': filename,
            'generator': 'htmlizer/%s' % (copyright.longversion,),
            'alternate': alternateLink % {'source': filename},
            'stylesheet': stylesheet
            })
        htmlizer.filter(open(filename), output,
                        htmlizer.SmallerHTMLWriter)
        output.write(footer)
    finally:
        output.close()
