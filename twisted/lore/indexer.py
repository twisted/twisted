# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


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
