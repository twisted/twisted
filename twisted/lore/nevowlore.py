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

"""
Nevow support for lore.

Do something like:

  lore -inevow --config pageclass=some.module.SomePageSubclass [other-opts]

API Stability: unstable

Maintainer: U{Christopher Armstrong<mailto:radix@twistedmatrix.com>}

"""

import os

from twisted.web import microdom
from twisted.python import reflect
from twisted.protocols import sux

from twisted.lore import default, tree, process

from nevow import rend

def parseStringAndReport(s):
    try:
        return microdom.parseString(s)
    except microdom.MismatchedTags, e:
        raise process.ProcessingFailure(
              "%s:%s: begin mismatched tags <%s>/</%s>" %
               (e.begLine, e.begCol, e.got, e.expect),
              "%s:%s: end mismatched tags <%s>/</%s>" %
               (e.endLine, e.endCol, e.got, e.expect))
    except microdom.ParseError, e:
        raise process.ProcessingFailure("%s:%s:%s" % (e.line, e.col, e.message))
    except IOError, e:
        raise process.ProcessingFailure(e.strerror)


def nevowify(filename, linkrel, ext, url, templ, options=None, outfileGenerator=tree.getOutputFileName):
    if options is None:
        options = {}
    pclass = options['pageclass']
    pclass = reflect.namedObject(pclass)
    page = pclass(docFactory=rend.htmlfile(filename))
    s = page.renderString()
    from twisted.trial.util import wait
    s = wait(s)

    newFilename = outfileGenerator(filename, ext)

    if options.has_key('nolore'):
        open(newFilename, 'w').write(s)
        return

    doc = parseStringAndReport(s)
    clonedNode = templ.cloneNode(1)
    tree.munge(doc, clonedNode, linkrel, os.path.dirname(filename), filename, ext,
               url, options, outfileGenerator)
    tree.makeSureDirectoryExists(newFilename)
    clonedNode.writexml(open(newFilename, 'wb'))

    

class NevowProcessorFactory:

    def getDoFile(self):
        return nevowify


    def generate_html(self, options, filenameGenerator=tree.getOutputFileName):
        n = default.htmlDefault.copy()
        n.update(options)
        options = n
        try:
            fp = open(options['template'])
            templ = microdom.parse(fp)
        except IOError, e:
            raise process.NoProcessorError(e.filename+": "+e.strerror)
        except sux.ParseError, e:
            raise process.NoProcessorError(str(e))
        df = lambda file, linkrel: self.getDoFile()(file, linkrel, options['ext'],
                                                    options['baseurl'], templ, options, filenameGenerator)
        return df


factory = NevowProcessorFactory()
