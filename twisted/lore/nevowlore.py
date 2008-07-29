# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""
Nevow support for lore. DEPRECATED.

Don't use this module, it will be removed in the release of Twisted
after 2.3. If you want static templating with Nevow, instantiate a
rend.Page() and call renderString (or renderSynchronously) yourself.

Do something like::

  lore -inevow --config pageclass=some.module.SomePageSubclass [other-opts]

Maintainer: Christopher Armstrong

"""

import warnings
warnings.warn("twisted.lore.nevowlore is deprecated. Please instantiate "
              "rend.Page and call renderString or renderSynchronously "
              "yourself.", DeprecationWarning, stacklevel=2)

import os

from twisted.web import microdom
from twisted.python import reflect
from twisted.web import sux

from twisted.lore import default, tree, process

from nevow import loaders

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

def ____wait(d):
    "."
    from twisted.internet import reactor
    from twisted.python import failure
    l = []
    d.addBoth(l.append)
    while not l:
        reactor.iterate()
    if isinstance(l[0], failure.Failure):
        l[0].raiseException()
    return l[0]

def nevowify(filename, linkrel, ext, url, templ, options=None, outfileGenerator=tree.getOutputFileName):
    if options is None:
        options = {}
    pclass = options['pageclass']
    pclass = reflect.namedObject(pclass)
    page = pclass(docFactory=loaders.htmlfile(filename))
    s = page.renderString()
    s = ____wait(s)

    newFilename = outfileGenerator(filename, ext)

    if options.has_key('nolore'):
        f = open(newFilename, 'w')
        f.write(s)
        f.close()
        return

    doc = parseStringAndReport(s)
    clonedNode = templ.cloneNode(1)
    tree.munge(doc, clonedNode, linkrel, os.path.dirname(filename), filename, ext,
               url, options, outfileGenerator)
    tree.makeSureDirectoryExists(newFilename)
    f = open(newFilename, 'wb')
    clonedNode.writexml(f)
    f.close()

    

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
