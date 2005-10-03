
"""
Simple insults-based widget library

API Stability: 0

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

import array

from twisted.conch.insults import insults
from twisted.python import text as tptext

class YieldFocus(Exception):
    """Input focus manipulation exception
    """

class BoundedTerminalWrapper(object):
    def __init__(self, terminal, width, height, xoff, yoff):
        self.width = width
        self.height = height
        self.xoff = xoff
        self.yoff = yoff
        self.terminal = terminal
        self.cursorForward = terminal.cursorForward
        self.selectCharacterSet = terminal.selectCharacterSet
        self.selectGraphicRendition = terminal.selectGraphicRendition
        self.saveCursor = terminal.saveCursor
        self.restoreCursor = terminal.restoreCursor

    def cursorPosition(self, x, y):
        return self.terminal.cursorPosition(
            self.xoff + min(self.width, x),
            self.yoff + min(self.height, y)
            )

    def cursorHome(self):
        return self.terminal.cursorPosition(
            self.xoff, self.yoff)

    def write(self, bytes):
        return self.terminal.write(bytes)

class Widget(object):
    focused = False

    def render(self, terminal):
        pass

    def sizeHint(self):
        return None

    def keystrokeReceived(self, keyID, modifier):
        if keyID == '\t':
            self.tabReceived(modifier)
        elif keyID == '\x7f':
            self.backspaceReceived()
        elif keyID in insults.FUNCTION_KEYS:
            self.functionKeyReceived(keyID, modifier)
        else:
            self.characterReceived(keyID, modifier)

    def tabReceived(self, modifier):
        # XXX TODO - Handle shift+tab
        raise YieldFocus()

    def focusReceived(self):
        """Called when focus is being given to this widget.

        May raise YieldFocus is this widget does not want focus.
        """
        self.focused = True

    def focusLost(self):
        self.focused = False

    def backspaceReceived(self):
        pass

    def functionKeyReceived(self, keyID, modifier):
        func = getattr(self, 'func_' + keyID.name, None)
        if func is not None:
            func(modifier)

    def characterReceived(self, keyID, modifier):
        pass

class ContainerWidget(Widget):
    """
    @ivar focusedChild: The contained widget which currently has
    focus, or None.
    """
    focusedChild = None
    focused = False

    def __init__(self):
        Widget.__init__(self)
        self.children = []

    def addChild(self, child):
        self.children.append(child)
        if self.focusedChild is None and self.focused:
            try:
                child.focusReceived()
            except YieldFocus:
                pass
            else:
                self.focusedChild = child

    def remChild(self, child):
        self.children.remove(child)

    def render(self, width, height, terminal):
        for ch in self.children:
            ch.render(width, height, terminal)

    def changeFocus(self):
        if self.focusedChild is not None:
            self.focusedChild.focusLost()
            focusedChild = self.focusedChild
            self.focusedChild = None
            try:
                curFocus = self.children.index(focusedChild) + 1
            except ValueError:
                raise YieldFocus()
        else:
            curFocus = 0
        while curFocus < len(self.children):
            try:
                self.children[curFocus].focusReceived()
            except YieldFocus:
                curFocus += 1
            else:
                self.focusedChild = self.children[curFocus]
                return
        # None of our children wanted focus
        raise YieldFocus()


    def focusReceived(self):
        self.changeFocus()
        self.focused = True


    def keystrokeReceived(self, keyID, modifier):
        if self.focusedChild is not None:
            try:
                self.focusedChild.keystrokeReceived(keyID, modifier)
            except YieldFocus:
                self.changeFocus()
        else:
            Widget.keystrokeReceived(self, keyID, modifier)


class TopWindow(ContainerWidget):
    focused = True

    def changeFocus(self):
        try:
            ContainerWidget.changeFocus(self)
        except YieldFocus:
            try:
                ContainerWidget.changeFocus(self)
            except YieldFocus:
                pass

    def keystrokeReceived(self, keyID, modifier):
        try:
            ContainerWidget.keystrokeReceived(self, keyID, modifier)
        except YieldFocus:
            self.changeFocus()


class AbsoluteBox(ContainerWidget):
    def moveChild(self, child, x, y):
        for n in range(len(self.children)):
            if self.children[n][0] is child:
                self.children[n] = (child, x, y)
                break
        else:
            raise ValueError("No such child", child)

    def render(self, width, height, terminal):
        for (ch, x, y) in self.children:
            wrap = BoundedTerminalWrapper(terminal, width - x, height - y, x, y)
            ch.render(width, height, wrap)


class _Box(ContainerWidget):
    TOP, CENTER, BOTTOM = range(3)

    def __init__(self, gravity=CENTER):
        ContainerWidget.__init__(self)
        self.gravity = gravity

    def sizeHint(self):
        height = 0
        width = 0
        for ch in self.children:
            hint = ch.sizeHint()
            if hint is None:
                return None

            if self.variableDimension == 0:
                width += hint[0]
                height = max(height, hint[1])
            else:
                width = max(width, hint[0])
                height += hint[1]

        return width, height


    def render(self, width, height, terminal):
        if not self.children:
            return

        greedy = 0
        wants = []
        for ch in self.children:
            hint = ch.sizeHint()
            if hint is None:
                greedy += 1
                wants.append(None)
            else:
                wants.append(hint[self.variableDimension])

        length = (width, height)[self.variableDimension]
        totalWant = sum([w for w in wants if w is not None])
        if greedy:
            leftForGreedy = int((length - totalWant) / greedy)

        widthOffset = heightOffset = 0

        for want, ch in zip(wants, self.children):
            if want is None:
                want = leftForGreedy

            subWidth, subHeight = width, height
            if self.variableDimension == 0:
                subWidth = want
            else:
                subHeight = want

            wrap = BoundedTerminalWrapper(
                terminal,
                subWidth,
                subHeight,
                widthOffset,
                heightOffset,
                )
            ch.render(subWidth, subHeight, wrap)
            if self.variableDimension == 0:
                widthOffset += want
            else:
                heightOffset += want


class HBox(_Box):
    variableDimension = 0

class VBox(_Box):
    variableDimension = 1


class Packer(ContainerWidget):
    def render(self, width, height, terminal):
        if not self.children:
            return

        root = int(len(self.children) ** 0.5 + 0.5)
        boxes = [VBox() for n in range(root)]
        for n, ch in enumerate(self.children):
            boxes[n % len(boxes)].addChild(ch)
        h = HBox()
        map(h.addChild, boxes)
        return h.render(width, height, terminal)


class Canvas(Widget):
    focused = False

    contents = None

    def __init__(self):
        Widget.__init__(self)
        self.resize(1, 1)

    def resize(self, width, height):
        contents = array.array('c', ' ' * width * height)
        if self.contents is not None:
            for x in range(min(width, self.width)):
                for y in range(min(height, self.height)):
                    contents[width * y + x] = self[x, y]
        self.contents = contents
        self.width = width
        self.height = height
        if self.x >= width:
            self.x = width - 1
        if self.y >= height:
            self.y = height - 1

    def __getitem__(self, (x, y)):
        return self.contents[(self.width * y) + x]

    def __setitem__(self, (x, y), value):
        self.contents[(self.width * y) + x] = value

    def clear(self):
        self.contents = array.array('c', ' ' * len(self.contents))

    def render(self, width, height, terminal):
        if not width or not height:
            return

        if width != self.width or height != self.height:
            self.resize(width, height)
        for i in range(height):
            terminal.cursorPosition(0, i)
            terminal.write(''.join(self.contents[self.width * i:self.width * i + self.width])[:width])


def rectangle(terminal, (top, left), (width, height)):
    terminal.selectCharacterSet(insults.CS_DRAWING, insults.G0)

    terminal.cursorPosition(top, left)
    terminal.write(chr(0154))
    terminal.write(chr(0161) * (width - 2))
    terminal.write(chr(0153))
    for n in range(height - 2):
        terminal.cursorPosition(left, top + n + 1)
        terminal.write(chr(0170))
        terminal.cursorForward(width - 2)
        terminal.write(chr(0170))
    terminal.cursorPosition(0, top + height - 1)
    terminal.write(chr(0155))
    terminal.write(chr(0161) * (width - 2))
    terminal.write(chr(0152))

    terminal.selectCharacterSet(insults.CS_US, insults.G0)

class Border(Widget):
    def __init__(self, containee):
        Widget.__init__(self)
        self.containee = containee

    def focusReceived(self):
        return self.containee.focusReceived()

    def focusLost(self):
        return self.containee.focusLost()

    def keystrokeReceived(self, keyID, modifier):
        return self.containee.keystrokeReceived(keyID, modifier)

    def sizeHint(self):
        hint = self.containee.sizeHint()
        if hint is not None:
            return hint[0] + 2, hint[1] + 2
        return None

    def render(self, width, height, terminal):
        rectangle(terminal, (0, 0), (width, height))
        wrap = BoundedTerminalWrapper(terminal, width - 2, height - 2, 1, 1)
        self.containee.render(width - 2, height - 2, wrap)


class Button(Widget):
    def __init__(self, label, onPress):
        Widget.__init__(self)

        self.label = label
        self.onPress = onPress

    def sizeHint(self):
        return len(self.label), 1

    def characterReceived(self, keyID, modifier):
        if keyID == '\r':
            self.onPress()

    def render(self, width, height, terminal):
        terminal.cursorPosition(0, 0)
        if self.focused:
            terminal.write('\x1b[1m' + self.label + '\x1b[0m')
        else:
            terminal.write(self.label)

class TextInput(Widget):
    def __init__(self, maxwidth, onSubmit):
        Widget.__init__(self)
        self.onSubmit = onSubmit
        self.maxwidth = maxwidth
        self.buffer = ''
        self.cursor = 0

    def setText(self, text):
        self.buffer = text[:self.maxwidth]
        self.cursor = len(self.buffer)

    def func_LEFT_ARROW(self, modifier):
        if self.cursor > 0:
            self.cursor -= 1

    def func_RIGHT_ARROW(self, modifier):
        if self.cursor < len(self.buffer):
            self.cursor += 1

    def backspaceReceived(self):
        if self.cursor > 0:
            self.buffer = self.buffer[:self.cursor - 1] + self.buffer[self.cursor:]
            self.cursor -= 1

    def characterReceived(self, keyID, modifier):
        if keyID == '\r':
            self.onSubmit(self.buffer)
        else:
            if len(self.buffer) < self.maxwidth:
                self.buffer = self.buffer[:self.cursor] + keyID + self.buffer[self.cursor:]
                self.cursor += 1

    def sizeHint(self):
        return self.maxwidth + 1, 1

    def render(self, width, height, terminal):
        currentText = self._renderText()
        terminal.cursorPosition(0, 0)
        if self.focused:
            terminal.write(currentText[:self.cursor])
            cursor(terminal, currentText[self.cursor:self.cursor+1] or ' ')
            terminal.write(currentText[self.cursor+1:])
            terminal.write(' ' * (self.maxwidth - len(currentText) + 1))
        else:
            more = self.maxwidth - len(currentText)
            terminal.write(currentText + '_' * more)

    def _renderText(self):
        return self.buffer

class PasswordInput(TextInput):
    def _renderText(self):
        return '*' * len(self.buffer)

class TextOutput(Widget):
    text = ''

    def __init__(self, size=None):
        Widget.__init__(self)
        self.size = size

    def sizeHint(self):
        return self.size

    def render(self, width, height, terminal):
        terminal.cursorPosition(0, 0)
        text = self.text[:width]
        terminal.write(text + ' ' * (width - len(text)))

    def setText(self, text):
        self.text = text

    def focusReceived(self):
        raise YieldFocus()

class TextOutputArea(TextOutput):
    WRAP, TRUNCATE = range(2)

    def __init__(self, size=None, longLines=WRAP):
        TextOutput.__init__(self, size)
        self.longLines = longLines

    def render(self, width, height, terminal):
        n = 0
        inputLines = self.text.splitlines()
        outputLines = []
        while inputLines:
            if self.longLines == self.WRAP:
                wrappedLines = tptext.greedyWrap(inputLines.pop(0), width)
                outputLines.extend(wrappedLines or [''])
            else:
                outputLines.append(inputLines.pop(0)[:width])
            if len(outputLines) >= height:
                break
        for n, L in enumerate(outputLines[:height]):
            terminal.cursorPosition(0, n)
            terminal.write(L)

def cursor(terminal, ch):
    terminal.saveCursor()
    terminal.selectGraphicRendition(str(insults.REVERSE_VIDEO))
    terminal.write(ch)
    terminal.restoreCursor()
    terminal.cursorForward()

class Selection(Widget):
    # Index into the sequence
    focusedIndex = 0

    # Offset into the displayed subset of the sequence
    renderOffset = 0

    def __init__(self, sequence, onSelect, minVisible=None):
        Widget.__init__(self)
        self.sequence = sequence
        self.onSelect = onSelect
        self.minVisible = minVisible
        if minVisible is not None:
            self._width = max(map(len, self.sequence))

    def sizeHint(self):
        if self.minVisible is not None:
            return self._width, self.minVisible

    def func_UP_ARROW(self, modifier):
        if self.focusedIndex > 0:
            self.focusedIndex -= 1
            if self.renderOffset > 0:
                self.renderOffset -= 1

    def func_PGUP(self, modifier):
        if self.renderOffset != 0:
            self.focusedIndex -= self.renderOffset
            self.renderOffset = 0
        else:
            self.focusedIndex = max(0, self.focusedIndex - self.height)

    def func_DOWN_ARROW(self, modifier):
        if self.focusedIndex < len(self.sequence) - 1:
            self.focusedIndex += 1
            if self.renderOffset < self.height - 1:
                self.renderOffset += 1


    def func_PGDN(self, modifier):
        if self.renderOffset != self.height - 1:
            change = self.height - self.renderOffset - 1
            if change + self.focusedIndex >= len(self.sequence):
                change = len(self.sequence) - self.focusedIndex - 1
            self.focusedIndex += change
            self.renderOffset = self.height - 1
        else:
            self.focusedIndex = min(len(self.sequence) - 1, self.focusedIndex + self.height)

    def characterReceived(self, keyID, modifier):
        if keyID == '\r':
            self.onSelect(self.sequence[self.focusedIndex])

    def render(self, width, height, terminal):
        self.height = height
        start = self.focusedIndex - self.renderOffset
        if start > len(self.sequence) - height:
            start = max(0, len(self.sequence) - height)

        elements = self.sequence[start:start+height]

        for n, ele in enumerate(elements):
            terminal.cursorPosition(0, n)
            if n == self.renderOffset:
                terminal.saveCursor()
                if self.focused:
                    modes = str(insults.REVERSE_VIDEO), str(insults.BOLD)
                else:
                    modes = str(insults.REVERSE_VIDEO),
                terminal.selectGraphicRendition(*modes)
            text = ele[:width]
            terminal.write(text + (' ' * (width - len(text))))
            if n == self.renderOffset:
                terminal.restoreCursor()
