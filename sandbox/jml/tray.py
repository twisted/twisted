from twisted.internet import gtk2reactor
gtk2reactor.install()

import gtk
import win32api, win32con, win32gui
import time

from twisted.internet import task


class Taskbar:
    def __init__(self):
        self.visible = 0
        message_map = {
            win32con.WM_DESTROY: self.onDestroy,
            win32con.WM_USER+20 : self.onTaskbarNotify,
        }
        # Register the Window class.
        wc = win32gui.WNDCLASS()
        hinst = wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = "PythonTaskbarDemo"
        wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        wc.hCursor = win32gui.LoadCursor( 0, win32con.IDC_ARROW )
        wc.hbrBackground = win32con.COLOR_WINDOW
        wc.lpfnWndProc = message_map # could also specify a wndproc.
        classAtom = win32gui.RegisterClass(wc)
        # Create the Window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow( classAtom, "Taskbar Demo", style, \
                    0, 0, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT, \
                    0, 0, hinst, None)
        win32gui.UpdateWindow(self.hwnd)

    def setIcon(self, hicon, tooltip=None):
        self.hicon = hicon
        self.tooltip = tooltip
        
    def show(self):
        """Display the taskbar icon"""
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE
        if self.tooltip is not None:
            flags |= win32gui.NIF_TIP
            nid = (self.hwnd, 0, flags, win32con.WM_USER+20, self.hicon, self.tooltip)
        else:
            nid = (self.hwnd, 0, flags, win32con.WM_USER+20, self.hicon)
        if self.visible:
            self.hide()
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
        self.visible = 1

    def hide(self):
        """Hide the taskbar icon"""
        if self.visible:
            nid = (self.hwnd, 0)
            win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        self.visible = 0
        
    def onDestroy(self, hwnd, msg, wparam, lparam):
        self.destroy()
        
    def destroy(self):
        self.hide()
        win32gui.PostQuitMessage(0) # Terminate the app.

    def onTaskbarNotify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_LBUTTONUP:
            self.onClick()
        elif lparam == win32con.WM_LBUTTONDBLCLK:
            self.onDoubleClick()
        elif lparam == win32con.WM_RBUTTONUP:
            self.onRightClick()
        return 1

    def onClick(self):
        """Override in subclassess"""
        pass

    def onDoubleClick(self):
        """Override in subclassess"""
        pass


class GtkTaskbar(Taskbar):
    def __init__(self, window=None, popup=None):
        Taskbar.__init__(self)
        self.window = window
        if self.window:
            self.window.hide()
        self.popup = popup
        self.win32eventloop = task.LoopingCall(win32gui.PumpWaitingMessages)
        self.win32eventloop.start(0.1)

    def destroy(self):
        Taskbar.destroy(self)
        self.win32eventloop.stop()

    def onClick(self):
        if self.window:
            if self.window.visible:
                self.window.hide()
            else:
                self.window.show()

    def onRightClick(self):
        if self.popup:
            win32gui.SetForegroundWindow(self.hwnd)
            self.popup.popup(None, None, None, 3, int(time.time()))


def shutdown(t):
    t.destroy()
    from twisted.internet import reactor
    reactor.stop()

def iconFromFile(filename):
    return win32gui.LoadImage(0, filename, win32con.IMAGE_ICON, 0, 0, win32con.LR_LOADFROMFILE|win32con.LR_DEFAULTSIZE)

def iconFromApp():
    return win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

if __name__=='__main__':
    from twisted.internet import reactor
    t = GtkTaskbar()
    t.popup = gtk.Menu()
    items = [ gtk.MenuItem(x) for x in [ 'item 1', 'item 2' ] ]
    for i in items:
        i.show()
        t.popup.append(i)
    t.setIcon(iconFromFile(r'c:\python23\pyc.ico'), 'test app')
    t.show()
    t.onDoubleClick = lambda : shutdown(t)

    reactor.run()
