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

"""
*S*mall, *U*ncomplicated *X*ML.

This is a very simple implementation of XML as a network protocol.  It is not
at all clever.  Its main features are that it does not:

  * support namespaces
  * mung mnemonic entity references
  * validate
  * perform *any* external actions (such as fetching URLs or writing files)
    under *any* circumstances

If you're looking for an XML parser that *does* do any of these things, I
strongly recommend the various parsers in PyXML.

TODO:

  * support comments
  * real tests

"""

from twisted.internet.protocol import Protocol, FileWrapper

import string

identChars = string.letters+string.digits+'.-_:'

def nop(*args, **kw):
    "Do nothing."
    

class XMLParser(Protocol):
    state = None
    def connectionMade(self):
        self.lineno = 1
        self.colno = 0

    def saveMark(self):
        return (self.lineno, self.colno)

    def dataReceived(self, data):
        if not self.state:
            self.state = 'begin'
        for byte in data:
            # do newline stuff
            if byte == '\n':
                self.lineno += 1
                self.colno = 0
            else:
                self.colno += 1
            oldState = self.state
            # print "%s: %s %s" % (self.state, repr(byte), self.saveMark())
            newState = getattr(self, "do_" + self.state)(byte)
            if newState and newState != oldState:
                #print oldState,'=>',newState
                self.state = newState
                getattr(self, "end_" + oldState, nop)()
                getattr(self, "begin_" + newState, nop)(byte)

    # state methods

    def do_begin(self, byte):
        if byte in string.whitespace:
            return
        if byte != '<':
            raise Exception("First char of document wasn't <")
        return 'tagstart'

    def begin_tagstart(self, byte):
        self.tagName = ''               # name of the tag
        self.tagAttributes = {}         # attributes of the tag
        self.termtag = 0                # is the tag self-terminating
        self.endtag = 0

    def do_tagstart(self, byte):
        if byte in identChars:
            self.tagName += byte
        elif byte in string.whitespace:
            if self.tagName:
                return 'attrs'
            else:
                raise Exception("no tag name")
        elif byte in '!?':
            if self.tagName:
                raise Exception("exclamation point!?")
            else:
                self.tagName += byte
                self.termtag = 1
        elif byte == '[':
            if self.tagName == '!':
                return 'expectcdata'
            else:
                raise Exception("hurk")
        elif byte == '/':
            if self.tagName:
                return 'afterslash'
            else:
                self.endtag = 1
        elif byte == '>':
            if self.endtag:
                self.gotTagEnd(self.tagName)
            else:
                self.gotTagStart(self.tagName, {})
            return 'bodydata'
        else:
            raise Exception(repr(byte))

    def begin_expectcdata(self, byte):
        self.cdatabuf = byte

    def do_expectcdata(self, byte):
        self.cdatabuf += byte
        cdb = self.cdatabuf
        cd = '[CDATA['
        if len(cd) > len(cdb):
            if cd.startswith(cdb):
                return
            else:
                raise Exception("Uh, cdata section looked hella malformed")
        if cd == cdb:
            self.cdatabuf = ''
            return 'cdata'
        raise Exception("uh, cdata looks badz0r")

    def do_cdata(self, byte):
        self.cdatabuf += byte
        if self.cdatabuf.endswith("]]>"):
            self.cdatabuf = self.cdatabuf[:-3]
            return 'bodydata'

    def end_cdata(self):
        self.gotCData(self.cdatabuf)
        self.cdatabuf = ''

    def do_attrs(self, byte):
        if byte in string.whitespace:
            return
        elif byte in identChars:
            # XXX FIXME really handle !DOCTYPE at some point
            if self.tagName[0] in '!?':
                return 'waitforgt'
            return 'attrname'
        elif byte == '/':
            return 'afterslash'
        elif byte == '>':
            self.gotTagStart(self.tagName, self.tagAttributes)
            return 'bodydata'
        raise Exception("not well formed, etc")

    def do_waitforgt(self, byte):
        if byte == '>':
            return 'bodydata'

    def begin_attrname(self, byte):
        self.attrname = byte

    def do_attrname(self, byte):
        if byte in identChars:
            self.attrname += byte
        elif byte in string.whitespace:
            return 'beforeeq'
        elif byte == '=':
            return 'beforeattrval'
        else:
            raise Exception("not well formed, etc")

    def do_beforeattrval(self, byte):
        if byte in string.whitespace:
            return
        elif byte in '"\'':
            return 'attrval'
        raise Exception("Not well formed, etc")

    def do_beforeeq(self, byte):
        if byte in string.whitespace:
            return
        elif byte == '=':
            return 'beforeattrval'
        raise Exception("Not well formed, etc")

    def begin_attrval(self, byte):
        self.quotetype = byte
        self.attrval = ''

    def do_attrval(self, byte):
        if byte == self.quotetype:
            return 'attrs'
        self.attrval += byte

    def end_attrval(self):
        self.tagAttributes[self.attrname] = self.attrval

    def begin_afterslash(self, byte):
        self._after_slash_closed = 0

    def do_afterslash(self, byte):
        # this state is only after a self-terminating slash, e.g. <foo/>
        if self._after_slash_closed:
            raise Exception("Not well formed, etc")
        if byte != '>':
            raise Exception("Not well formed, etc")
        self._after_slash_closed = 1
        self.gotTagStart(self.tagName, self.tagAttributes)
        self.gotTagEnd(self.tagName)
        return 'bodydata'

    def begin_bodydata(self, byte):
        self.bodydata = ''

    def do_bodydata(self, byte):
        if byte == '<':
            return 'tagstart'
        if byte == '&':
            return 'entityref'
        self.bodydata += byte

    def end_bodydata(self):
        self.gotText(self.bodydata)
        self.bodydata = ''

    def begin_entityref(self, byte):
        self.erefbuf = ''

    def do_entityref(self, byte):
        if byte != ';':
            self.erefbuf += byte
        else:
            return 'bodydata'

    def end_entityref(self):
        self.gotEntityReference(self.erefbuf)

    # Sorta SAX-ish API
    
    def gotTagStart(self, name, attributes):
        print 'begin', name, attributes

    def gotText(self, data):
        print 'text:', repr(data)

    def gotEntityReference(self, entityRef):
        print 'entityRef: &%s;' % entityRef

    def gotCData(self, cdata):
        print 'CDATA:', repr(cdata)

    def gotTagEnd(self, name):
        print 'end', name

if __name__ == '__main__':
    from cStringIO import StringIO
    testDocument = '''
    
    <!DOCTYPE ignore all this shit, hah its malformed!!!!@$>
    <?xml version="suck it"?>
    <foo>
    <bar />
    <baz boz="buz">boz &zop;</baz>
    <![CDATA[ foo bar baz ]]>
    </foo>
    '''
    x = XMLParser()
    x.makeConnection(FileWrapper(StringIO()))
    # fn = "/home/glyph/Projects/Twisted/doc/howto/ipc10paper.html"
    fn = "/home/glyph/gruesome.xml"
    # testDocument = open(fn).read()
    x.dataReceived(testDocument)
