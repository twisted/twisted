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

  - support namespaces
  - mung mnemonic entity references
  - validate
  - perform *any* external actions (such as fetching URLs or writing files)
    under *any* circumstances

If you're looking for an XML parser that *does* do any of these things, I
strongly recommend the various parsers in PyXML.

TODO:

  - real tests (currently we're just hoping Marmalade tests are good enough)
  - better error messages

"""

from twisted.internet.protocol import Protocol, FileWrapper

import string

identChars = string.letters+string.digits+'.-_:'
lenientIdentChars = identChars + ';+#'

def nop(*args, **kw):
    "Do nothing."
    
class ParseError(Exception):

    def __init__(self, filename, line, col, message):
        self.filename = filename
        self.line = line
        self.col = col
        self.message = message

    def __str__(self):
       return "%s:%s:%s: %s" % (self.filename, self.line, self.col,
                                self.message)


class XMLParser(Protocol):

    state = None
    filename = "<xml />"
    beExtremelyLenient = 0

    def connectionMade(self):
        self.lineno = 1
        self.colno = 0

    def saveMark(self):
        '''Get the line number and column of the last character parsed'''
        return (self.lineno, self.colno)

    def _parseError(self, message):
        raise ParseError(*((self.filename,)+self.saveMark()+(message,)))

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
            newState = getattr(self, "do_" + self.state)(byte)
            if newState and newState != oldState:
                self.state = newState
                getattr(self, "end_" + oldState, nop)()
                getattr(self, "begin_" + newState, nop)(byte)

    # state methods

    def do_begin(self, byte):
        if byte in string.whitespace:
            return
        if byte != '<':
            self._parseError("First char of document wasn't <")
        return 'tagstart'

    def begin_tagstart(self, byte):
        self.tagName = ''               # name of the tag
        self.tagAttributes = {}         # attributes of the tag
        self.termtag = 0                # is the tag self-terminating
        self.endtag = 0

    def begin_comment(self, byte):
        self.commentbuf = ''

    def do_comment(self, byte):
        self.commentbuf += byte
        if self.commentbuf[-3:] == '-->':
            self.gotComment(self.commentbuf[:-3])
            return 'bodydata'

    def do_tagstart(self, byte):
        if byte in identChars:
            self.tagName += byte
            if self.tagName =='!--':
                return 'comment'
        elif byte in string.whitespace:
            if self.tagName:
                if self.endtag:
                    # properly strict thing to do here is probably to only
                    # accept whitespace
                    return 'waitforgt'
                return 'attrs'
            else:
                self._parseError("Whitespace before tag-name")
        elif byte in '!?':
            if self.tagName:
                self._parseError("Invalid character in tag-name")
            else:
                self.tagName += byte
                self.termtag = 1
        elif byte == '[':
            if self.tagName == '!':
                return 'expectcdata'
            else:
                self._parseError("Invalid '[' in tag-name")
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
            self._parseError('Invalid tag character: %r'% byte)

    def begin_expectcdata(self, byte):
        self.cdatabuf = byte

    def do_expectcdata(self, byte):
        self.cdatabuf += byte
        cdb = self.cdatabuf
        cd = '[CDATA['
        if len(cd) > len(cdb):
            if cd.startswith(cdb):
                return
            elif self.beExtremelyLenient:
                ## WHAT THE CRAP!?  MSWord9 generates HTML that includes these
                ## bizarre <![if !foo]> <![endif]> chunks, so I've gotta ignore
                ## 'em as best I can.  this should really be a separate parse
                ## state but I don't even have any idea what these _are_.
                return 'waitforgt'
            else:
                self._parseError("Mal-formed CDATA header")
        if cd == cdb:
            self.cdatabuf = ''
            return 'cdata'
        self._parseError("Mal-formed CDATA header")

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
            if self.tagName == '!DOCTYPE':
                return 'doctype'
            if self.tagName[0] in '!?':
                return 'waitforgt'
            return 'attrname'
        elif byte == '/':
            return 'afterslash'
        elif byte == '>':
            self.gotTagStart(self.tagName, self.tagAttributes)
            return 'bodydata'
        elif self.beExtremelyLenient:
            # discard and move on?  Only case I've seen of this so far was:
            # <foo bar="baz"">
            return
        self._parseError("Unexpected character: %r" % byte)

    def begin_doctype(self, byte):
        self.doctype = byte

    def do_doctype(self, byte):
        if byte == '>':
            return 'bodydata'
        self.doctype += byte

    def end_doctype(self):
        self.gotDoctype(self.doctype)
        self.doctype = None

    def do_waitforgt(self, byte):
        if byte == '>':
            return 'bodydata'

    def begin_attrname(self, byte):
        self.attrname = byte
        self._attrname_termtag = 0

    def do_attrname(self, byte):
        if byte in identChars:
            self.attrname += byte
            return
        elif byte in string.whitespace:
            return 'beforeeq'
        elif byte == '=':
            return 'beforeattrval'
        elif self.beExtremelyLenient:
            if byte in '"\'':
                return 'attrval'
            if byte in lenientIdentChars:
                self.attrname += byte
                return
            if byte == '/':
                self._attrname_termtag = 1
                return
            if byte == '>':
                self.attrval = 'True'
                self.tagAttributes[self.attrname] = self.attrval
                self.gotTagStart(self.tagName, self.tagAttributes)
                if self._attrname_termtag:
                    self.gotTagEnd(self.tagName)
                return 'bodydata'
        self._parseError("Invalid attribute name: %r %r" % (self.attrname, byte))

    def do_beforeattrval(self, byte):
        if byte in string.whitespace:
            return
        elif byte in '"\'':
            return 'attrval'
        elif self.beExtremelyLenient and byte in lenientIdentChars:
            return 'messyattr'
        self._parseError("Invalid intial attribute value: %r" % byte)

    attrname = ''
    attrval = ''

    def begin_beforeeq(self,byte):
        self._beforeeq_termtag = 0

    def do_beforeeq(self, byte):
        if byte in string.whitespace:
            return
        elif byte == '=':
            return 'beforeattrval'
        elif self.beExtremelyLenient:
            if byte in identChars:
                self.attrval = 'True'
                self.tagAttributes[self.attrname] = self.attrval
                return 'attrname'
            elif byte == '>':
                self.attrval = 'True'
                self.tagAttributes[self.attrname] = self.attrval
                self.gotTagStart(self.tagName, self.tagAttributes)
                if self._beforeeq_termtag:
                    self.gotTagEnd(self.tagName)
                return 'bodydata'
            elif byte == '/':
                self._beforeeq_termtag = 1
                return
        self._parseError("Invalid attribute")

    def begin_attrval(self, byte):
        self.quotetype = byte
        self.attrval = ''

    def do_attrval(self, byte):
        if byte == self.quotetype:
            return 'attrs'
        self.attrval += byte

    def end_attrval(self):
        self.tagAttributes[self.attrname] = self.attrval
        self.attrname = ''
        self.attrval = ''

    def begin_messyattr(self, byte):
        self.attrval = byte

    def do_messyattr(self, byte):
        if byte in string.whitespace:
            return 'attrs'
        elif byte == '>':
            endTag = 0
            if self.attrval[-1] == '/':
                endTag = 1
                self.attrval = self.attrval[:-1]
            self.tagAttributes[self.attrname]=self.attrval
            self.gotTagStart(self.tagName, self.tagAttributes)
            if endTag:
                self.gotTagEnd(self.tagName)
            return 'bodydata'
        else:
            self.attrval += byte

    def end_messyattr(self):
        if self.attrval:
            self.tagAttributes[self.attrname] = self.attrval

    def begin_afterslash(self, byte):
        self._after_slash_closed = 0

    def do_afterslash(self, byte):
        # this state is only after a self-terminating slash, e.g. <foo/>
        if self._after_slash_closed:
            self._parseError("Mal-formed")#XXX When does this happen??
        if byte != '>':
            self._parseError("No data allowed after '/'")
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
        if byte in string.whitespace:
            if self.beExtremelyLenient:
                self.erefbuf = "amp"
                return 'bodydata'
            self._parseError("Bad entity reference")
        if byte != ';':
            self.erefbuf += byte
        else:
            return 'bodydata'

    def end_entityref(self):
        self.gotEntityReference(self.erefbuf)

    # Sorta SAX-ish API
    
    def gotTagStart(self, name, attributes):
        '''Encountered an opening tag.

        Default behaviour is to print.'''
        print 'begin', name, attributes

    def gotText(self, data):
        '''Encountered text

        Default behaviour is to print.'''
        print 'text:', repr(data)

    def gotEntityReference(self, entityRef):
        '''Encountered mnemonic entity reference

        Default behaviour is to print.'''
        print 'entityRef: &%s;' % entityRef

    def gotComment(self, comment):
        '''Encountered mnemonic entity reference

        Default behaviour is to print.'''
        pass

    def gotCData(self, cdata):
        '''Encountered CDATA

        Default behaviour is to call the gotText method'''
        self.gotText(cdata)

    def gotDoctype(self, doctype):
        """Encountered DOCTYPE

        This is really grotty: it basically just gives you everything between
        '<!DOCTYPE' and '>' as an argument.
        """
        print '!DOCTYPE', repr(doctype)

    def gotTagEnd(self, name):
        '''Encountered closing tag

        Default behaviour is to print.'''
        print 'end', name

from HTMLParser import HTMLParser

import HTMLParser as htmlp
import re
htmlp.attrfind = re.compile(
    r'\s*([a-zA-Z_][-.,:a-zA-Z_0-9]*)(\s*=\s*'
    r'(\'[^\']*\'|"[^"]*"|[-a-zA-Z0-9./,:;+*%?!&$\(\)_#=~]*))?',
    re.MULTILINE)


class HTMLParserTranslator(HTMLParser):
    def __init__(self, xmlparser):
        self.xmlparser = xmlparser
        xmlparser.saveMark = self.getpos
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        d = {}
        for k, v in attrs:
            if v is None:
                v = 'True'
            d[k] = v
        self.xmlparser.gotTagStart(tag, d)

    def handle_endtag(self, tag):
        self.xmlparser.gotTagEnd(tag)

    def handle_charref(self, name):
        self.xmlparser.gotEntityReference("#"+name)

    def handle_entityref(self, name):
        self.xmlparser.gotEntityReference(name)

    def handle_data(self, data):
        self.xmlparser.gotText(data)

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self.xmlparser.gotDoctype(decl[len('doctype '):])

    def handle_comment(self, comment):
        self.xmlparser.gotComment(comment)

    def makeConnection(self, other):
        self.xmlparser.makeConnection(other)

    def dataReceived(self, data):
        self.feed(data)

    def close(self, reason=None):
        HTMLParser.close(self)
        self.xmlparser.connectionLost(reason)

    connectionLost = close


if __name__ == '__main__':
    from cStringIO import StringIO
    testDocument = '''
    
    <!DOCTYPE ignore all this shit, hah its malformed!!!!@$>
    <?xml version="suck it"?>
    <foo>
    &#65;
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
