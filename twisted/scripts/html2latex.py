# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

import os
from twisted.lore import latex, texi, docbook
from twisted.python import usage

class Options(usage.Options):

    optFlags = [['section', 's', 'Generate a section, not an article'],
                ['texi', 'i', 'Generate a Texinfo section'],
                ['docbook', 'c', 'Generate a Docbook section']]

    optParameters = [['dir', 'd', None, 'Directory relative to which references'
                                        ' will be taken']]

    def parseArgs(self, *files):
        self['files'] = files

def run():
    opt = Options()
    opt.parseOptions()
    ext = ".tex"
    if opt['section']:
        klass = latex.SectionLatexSpitter
    elif opt['texi']:
        klass = texi.TexiSpitter
        ext = '.texinfo'
    elif opt['docbook']:
        klass = docbook.DocbookSpitter
        ext = '.xml'
    else:
        klass = latex.LatexSpitter
    for file in opt['files']:
        fout = open(os.path.splitext(file)[0]+ext, 'w')
        dir = opt['dir'] or os.path.dirname(file)
        spitter = klass(fout.write, dir, os.path.basename(file))
        latex.processFile(spitter, open(file))
