
import helper
import insults

class _Attribute(object):
    def __getitem__(self, item):
        assert isinstance(item, (_Attribute, str))
        self.children.append(item)

    def serialize(self, write, attrs):
        for ch in self.children:
            if isinstance(ch, str):
                write(ch)
            else:
                ch.serialize(write, attrset)

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

class _OtherAttr(_Attribute):
    def __init__(self, attrname, attrvalue):
        self.attrname = attrname
        self.attrvalue = attrvalue

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
            write(a.toVT102())

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

    fg = _ColorAttributes(_ForegroundColorAttr)
    bg = _ColorAttributes(_BackgroundColorAttr)

    attrs = {
        'bold': insults.BOLD,
        'blink': insults.BLINK,
        'underline': insults.UNDERLINE,
        'reverseVideo': insults.REVERSE_VIDEO,
        'normal': insults.NORMAL}

    def __getattr__(self, name):
        try:
            return _Attribute(self.attrs[name])
        except KeyError:
            raise AttributeError(name)
