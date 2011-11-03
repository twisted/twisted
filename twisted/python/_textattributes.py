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
            attrs = DefaultCharacterAttribute()
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



class _ColorAttribute(object):
    def __init__(self, ground, attrs):
        self.ground = ground
        self.attrs = attrs

    def __getattr__(self, name):
        try:
            return self.ground(self.attrs[name])
        except KeyError:
            raise AttributeError(name)



class CharacterAttributesMixin(object):
    def __getattr__(self, name):
        if name == 'normal':
            return _NormalAttr()
        if name in self.attrs:
            return _OtherAttr(name, True)
        raise AttributeError(name)



class DefaultCharacterAttribute(object, FancyEqMixin):
    """
    A character attribute that does nothing, thus applying no attributes to
    text.
    """
    compareAttributes = ('_dummy',)

    _dummy = 0


    def copy(self):
        """
        Make a copy of this character attribute.
        """
        return type(self)()


    def wantOne(self, **kw):
        return self.copy()


    def toVT102(self):
        """
        Emit a VT102 control sequence that will set up all the attributes this
        character attribute has set.
        """
        return ''



class CharacterAttributeMixin(DefaultCharacterAttribute):
    """
    Mixin for the attributes of a single character.
    """
    def copy(self):
        c = DefaultCharacterAttribute.copy(self)
        c.__dict__.update(vars(self))
        return c


    def wantOne(self, **kw):
        k, v = kw.popitem()
        if getattr(self, k) != v:
            attr = self.copy()
            attr._subtracting = not v
            setattr(attr, k, v)
            return attr
        else:
            return self.copy()



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

    @param attrs: A L{twisted.python._textattributes.CharacterAttribute}
        instance.

    @type attributeRenderer: C{str}
    @param attributeRenderer: Name of the method on L{attrs} that should be
        called to render the attributes during serialization. Defaults to
        C{'toVT102'}.

    @return: A VT102-friendly string
    """
    L = []
    output.serialize(L.append, attrs, attributeRenderer)
    return ''.join(L)



__all__ = [
    'flatten', 'DefaultCharacterAttribute', 'CharacterAttributesMixin']
