
import helper
import insults

class _Attribute(object):
    def __getitem__(self, item):
        assert isinstance(item, (tuple, _Attribute, str))
        if isinstance(item, tuple):
            self.children.extend(item)
        else:
            self.children.append(item)
        return self

    def serialize(self, write, attrs):
        for ch in self.children:
            if isinstance(ch, str):
                write(ch)
            else:
                ch.serialize(write, attrs)

class _ColorAttr(_Attribute):
    def __init__(self, color, ground):
        self.color = color
        self.ground = ground
        self.children = []

    def serialize(self, write, attrs):
        if not self.children:
            return

        if getattr(attrs, self.ground) != self.color:
            write("\x1b[%dm" % (self.color,))
            setattr(attrs, self.ground, self.color)

        super(_ColorAttr, self).serialize(write, attrs)

class _NormalAttr(_Attribute):
    def __init__(self):
        self.children = []

    def serialize(self, write, attrs):
        if not self.children:
            return

        if helper.CharacterAttribute() != attrs:
            write('\x1b[m')
            attrs.__init__()
        super(_NormalAttr, self).serialize(write, attrs)

class _OtherAttr(_Attribute):
    def __init__(self, attrname, attrvalue):
        self.attrname = attrname
        self.attrvalue = attrvalue
        self.children = []

    def __neg__(self):
        return _OtherAttr(self.attrname, not self.attrvalue)

    def serialize(self, write, attrs):
        if not self.children:
            return

        if getattr(attrs, self.attrname) and not self.attrvalue:
            # We have to turn everything off, then turn back on everything
            # except this one attribute.
            setattr(attrs, self.attrname, False)
            write(attrs.toVT102(only=True))
        elif not getattr(attrs, self.attrname) and self.attrvalue:
            # We just need to turn on one little thing.
            a = helper.CharacterAttribute()
            setattr(a, self.attrname, True)
            setattr(attrs, self.attrname, True)
            write(a.toVT102(only=False))

        super(_OtherAttr, self).serialize(write, attrs)

class _ForegroundColorAttr(_Attribute):
    def __init__(self, color):
        _Attribute.__init__(self, color, helper.FOREGROUND)

class _BackgroundColorAttr(_Attribute):
    def __init__(self, color):
        _Attribute.__init__(self, color, helper.BACKGROUND)

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
