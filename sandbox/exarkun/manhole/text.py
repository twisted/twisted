
import helper
import insults

class _Attribute(object):
    def __init__(self):
        self.children = []

    def __getitem__(self, item):
        assert isinstance(item, (tuple, _Attribute, str))
        if isinstance(item, tuple):
            self.children.extend(item)
        else:
            self.children.append(item)
        return self

    def serialize(self, write, attrs=None):
        if attrs is None:
            attrs = helper.CharacterAttribute()
        for ch in self.children:
            if isinstance(ch, str):
                write(attrs.toVT102())
                write(ch)
            else:
                ch.serialize(write, attrs.copy())

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
        try:
            return _OtherAttr(name, True)
        except KeyError:
            raise AttributeError(name)

def flatten(output, attrs):
    L = []
    output.serialize(L.append, attrs)
    return ''.join(L)

attributes = CharacterAttributes()
