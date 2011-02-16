# -*- test-case-name: twisted.conch.test.test_text -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Character attribute manipulation API

This module provides a domain-specific language (using Python syntax)
for the creation of text with additional display attributes associated
with it.  It is intended as an alternative to manually building up
strings containing ECMA 48 character attribute control codes.  It
currently supports foreground and background colors (black, red,
green, yellow, blue, magenta, cyan, and white), intensity selection,
underlining, blinking and reverse video.  Character set selection
support is planned.

Character attributes are specified by using two Python operations:
attribute lookup and indexing.  For example, the string \"Hello
world\" with red foreground and all other attributes set to their
defaults, assuming the name twisted.conch.insults.text.attributes has
been imported and bound to the name \"A\" (with the statement C{from
twisted.conch.insults.text import attributes as A}, for example) one
uses this expression::

 | A.fg.red[\"Hello world\"]

Other foreground colors are set by substituting their name for
\"red\".  To set both a foreground and a background color, this
expression is used::

 | A.fg.red[A.bg.green[\"Hello world\"]]

Note that either A.bg.green can be nested within A.fg.red or vice
versa.  Also note that multiple items can be nested within a single
index operation by separating them with commas::

 | A.bg.green[A.fg.red[\"Hello\"], " ", A.fg.blue[\"world\"]]

Other character attributes are set in a similar fashion.  To specify a
blinking version of the previous expression::

 | A.blink[A.bg.green[A.fg.red[\"Hello\"], " ", A.fg.blue[\"world\"]]]

C{A.reverseVideo}, C{A.underline}, and C{A.bold} are also valid.

A third operation is actually supported: unary negation.  This turns
off an attribute when an enclosing expression would otherwise have
caused it to be on.  For example::

 | A.underline[A.fg.red[\"Hello\", -A.underline[\" world\"]]]

@author: Jp Calderone
"""

from twisted.conch.insults import helper, insults

class _Attribute(object):
    def __init__(self):
        self.children = []

    def __getitem__(self, item):
        assert isinstance(item, (list, tuple, _Attribute, str))
        if isinstance(item, (list, tuple)):
            self.children.extend(item)
        else:
            self.children.append(item)
        return self

    def serialize(self, write, attrs=None):
        if attrs is None:
            attrs = helper.CharacterAttribute()
        for ch in self.children:
            if isinstance(ch, _Attribute):
                ch.serialize(write, attrs.copy())
            else:
                write(attrs.toVT102())
                write(ch)

class _NormalAttr(_Attribute):
    def serialize(self, write, attrs):
        attrs.__init__()
        super(_NormalAttr, self).serialize(write, attrs)

class _OtherAttr(_Attribute):
    def __init__(self, attrname, attrvalue):
        self.attrname = attrname
        self.attrvalue = attrvalue
        self.children = []

    def __neg__(self):
        result = _OtherAttr(self.attrname, not self.attrvalue)
        result.children.extend(self.children)
        return result

    def serialize(self, write, attrs):
        attrs = attrs.wantOne(**{self.attrname: self.attrvalue})
        super(_OtherAttr, self).serialize(write, attrs)

class _ColorAttr(_Attribute):
    def __init__(self, color, ground):
        self.color = color
        self.ground = ground
        self.children = []

    def serialize(self, write, attrs):
        attrs = attrs.wantOne(**{self.ground: self.color})
        super(_ColorAttr, self).serialize(write, attrs)

class _ForegroundColorAttr(_ColorAttr):
    def __init__(self, color):
        super(_ForegroundColorAttr, self).__init__(color, 'foreground')

class _BackgroundColorAttr(_ColorAttr):
    def __init__(self, color):
        super(_BackgroundColorAttr, self).__init__(color, 'background')

class CharacterAttributes(object):
    class _ColorAttribute(object):
        def __init__(self, ground):
            self.ground = ground

        attrs = {
            'black': helper.BLACK,
            'red': helper.RED,
            'green': helper.GREEN,
            'yellow': helper.YELLOW,
            'blue': helper.BLUE,
            'magenta': helper.MAGENTA,
            'cyan': helper.CYAN,
            'white': helper.WHITE}

        def __getattr__(self, name):
            try:
                return self.ground(self.attrs[name])
            except KeyError:
                raise AttributeError(name)

    fg = _ColorAttribute(_ForegroundColorAttr)
    bg = _ColorAttribute(_BackgroundColorAttr)

    attrs = {
        'bold': insults.BOLD,
        'blink': insults.BLINK,
        'underline': insults.UNDERLINE,
        'reverseVideo': insults.REVERSE_VIDEO}

    def __getattr__(self, name):
        if name == 'normal':
            return _NormalAttr()
        if name in self.attrs:
            return _OtherAttr(name, True)
        raise AttributeError(name)

def flatten(output, attrs):
    """Serialize a sequence of characters with attribute information

    The resulting string can be interpreted by VT102-compatible
    terminals so that the contained characters are displayed and, for
    those attributes which the terminal supports, have the attributes
    specified in the input.

    For example, if your terminal is VT102 compatible, you might run
    this for a colorful variation on the \"hello world\" theme::

     | from twisted.conch.insults.text import flatten, attributes as A
     | from twisted.conch.insults.helper import CharacterAttribute
     | print flatten(
     |     A.normal[A.bold[A.fg.red['He'], A.fg.green['ll'], A.fg.magenta['o'], ' ',
     |                     A.fg.yellow['Wo'], A.fg.blue['rl'], A.fg.cyan['d!']]],
     |     CharacterAttribute())

    @param output: Object returned by accessing attributes of the
    module-level attributes object.

    @param attrs: A L{twisted.conch.insults.helper.CharacterAttribute}
    instance

    @return: A VT102-friendly string
    """
    L = []
    output.serialize(L.append, attrs)
    return ''.join(L)

attributes = CharacterAttributes()

__all__ = ['attributes', 'flatten']
