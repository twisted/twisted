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
from twisted.python.util import FancyEqMixin



class _Attribute(object, FancyEqMixin):
    compareAttributes = ('children',)

    def __init__(self):
        self.children = []


    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, vars(self))


    def __getitem__(self, item):
        assert isinstance(item, (list, tuple, _Attribute, str))
        if isinstance(item, (list, tuple)):
            self.children.extend(item)
        else:
            self.children.append(item)
        return self


    def serialize(self, write, attrs=None, attributeRenderer='toVT102'):
        if attrs is None:
            attrs = helper.CharacterAttribute()
        for ch in self.children:
            if isinstance(ch, _Attribute):
                ch.serialize(write, attrs.copy(), attributeRenderer)
            else:
                renderMeth = getattr(attrs, attributeRenderer)
                write(renderMeth())
                write(ch)



class _NormalAttr(_Attribute):
    def serialize(self, write, attrs, attributeRenderer):
        attrs.__init__()
        _Attribute.serialize(self, write, attrs, attributeRenderer)



class _OtherAttr(_Attribute):
    compareAttributes = ('attrname', 'attrvalue', 'children')

    def __init__(self, attrname, attrvalue):
        _Attribute.__init__(self)
        self.attrname = attrname
        self.attrvalue = attrvalue


    def __neg__(self):
        result = _OtherAttr(self.attrname, not self.attrvalue)
        result.children.extend(self.children)
        return result


    def serialize(self, write, attrs, attributeRenderer):
        attrs = attrs.wantOne(**{self.attrname: self.attrvalue})
        _Attribute.serialize(self, write, attrs, attributeRenderer)


class _ColorAttr(_Attribute):
    compareAttributes = ('color', 'ground', 'children')

    def __init__(self, color, ground):
        _Attribute.__init__(self)
        self.color = color
        self.ground = ground


    def serialize(self, write, attrs, attributeRenderer):
        attrs = attrs.wantOne(**{self.ground: self.color})
        _Attribute.serialize(self, write, attrs, attributeRenderer)


class _ForegroundColorAttr(_ColorAttr):
    def __init__(self, color):
        _ColorAttr.__init__(self, color, 'foreground')



class _BackgroundColorAttr(_ColorAttr):
    def __init__(self, color):
        _ColorAttr.__init__(self, color, 'background')



_TEXT_COLORS = {
    'black': helper.BLACK,
    'red': helper.RED,
    'green': helper.GREEN,
    'yellow': helper.YELLOW,
    'blue': helper.BLUE,
    'magenta': helper.MAGENTA,
    'cyan': helper.CYAN,
    'white': helper.WHITE}



class _ColorAttribute(object):
    def __init__(self, ground, attrs):
        self.ground = ground
        self.attrs = attrs

    def __getattr__(self, name):
        try:
            return self.ground(self.attrs[name])
        except KeyError:
            raise AttributeError(name)



class CharacterAttributes(object):
    fg = _ColorAttribute(_ForegroundColorAttr, _TEXT_COLORS)
    bg = _ColorAttribute(_BackgroundColorAttr, _TEXT_COLORS)

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



def flatten(output, attrs, attributeRenderer='toVT102'):
    """
    Serialize a sequence of characters with attribute information

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

    @type attributeRenderer: C{str}
    @param attributeRenderer: Name of the method on L{attrs} that should be
        called to render the attributes during serialization. Defaults to
        C{'toVT102'}.

    @return: A VT102-friendly string
    """
    L = []
    output.serialize(L.append, attrs, attributeRenderer)
    return ''.join(L)

attributes = CharacterAttributes()

__all__ = ['attributes', 'flatten']
