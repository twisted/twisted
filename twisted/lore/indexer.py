# Twisted, the Framework of Your Internet
# Copyright (C) 2004 Matthew W. Lefkowitz
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

def setIndexFilename(filename='index.xhtml'):
    global indexFilename
    indexFilename = filename

def getIndexFilename():
    global indexFilename
    return indexFilename

def addEntry(filename, anchor, text, reference):
    global entries
    if not entries.has_key(text):
        entries[text] = []
    entries[text].append((filename, anchor, reference))

def clearEntries():
    global entries
    entries = {}

def generateIndex():
    global entries
    global indexFilename

    if not indexFilename:
        return

    f = open(indexFilename, 'w')
    sortedEntries = [(e.lower(), e) for e in entries]
    sortedEntries.sort()
    sortedEntries = [e[1] for e in sortedEntries]
    for text in sortedEntries:
        refs = []
        f.write(text.replace('!', ', ') + ': ')
        for (file, anchor, reference) in entries[text]:
            refs.append('<a href="%s#%s">%s</a>' % (file, anchor, reference))
        if text == 'infinite recursion':
            refs.append('<em>See Also:</em> recursion, infinite\n')
        if text == 'recursion!infinite':
            refs.append('<em>See Also:</em> infinite recursion\n')
        f.write('%s<br />\n' % ", ".join(refs))
    f.close()

def reset():
    clearEntries()
    setIndexFilename()

reset()
