#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys
from twisted.python import filepath

def updateDocumentation(project, twistedCheckoutPath, websiteCheckoutPath):
    """
    Copy documentation for a particular project out of the craphole where lore
    dumps it, and into a WebSite working copy.

    @param generatedDocPath: The path to the root of a Twisted checkout, ie
    ~/Projects/Twisted/tags/releases/TwistedWeb/0.5.x/

    @param websiteCheckoutPath: The path to the root of a WebSite checkout, ie
    ~/Projects/WebSite/branches/update-web-docs-123/
    """
    docPath = twistedCheckoutPath.child('doc').child(project)
    minusSVN = docPath.temporarySibling()
    docPath.copyTo(minusSVN)
    for child in minusSVN.walk():
        if child.basename() == '.svn':
            child.remove()

    minusSVN.copyTo(websiteCheckoutPath.child('vhosts').child('twistedmatrix.com').child('projects').child(project).child('documentation'))
    minusSVN.remove()


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit("Usage: %s <project> <twisted checkout root> <website checkout root>" % (sys.argv[0],))
    updateDocumentation(sys.argv[1], filepath.FilePath(sys.argv[2]), filepath.FilePath(sys.argv[3]))
