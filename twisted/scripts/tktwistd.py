
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""Implementation module for the graphical version of the `twistd` command.
"""

# System imports
import os
import Tkinter, tkFileDialog, tkMessageBox

# Sibling imports
import twistd, tkmktap, tapconvert

# Twisted imports
from twisted.internet import tksupport, reactor

FILE_TYPES = (
    ('Twisted Application Pickle', '*.tap'),
    ('Twisted Application Source', '*.tas'),
    ('Twisted Application XML', '*.tax'),
    ('Encrypted Application Pickle', '*.etap'),
    ('Encrypted Application Source', '*.etas'),
    ('Encrypted Application XML', '*.etax'),
    ('All Files', '*')
)

class TkTwistdMenu(Tkinter.Menu):
    def __init__(self, master, launch):
        Tkinter.Menu.__init__(self, master)
        
        cmdMenu = Tkinter.Menu(self)
        self.add_cascade(label="Actions", menu=cmdMenu)
        
        cmdMenu.add_command(label="Launch", command=launch)
        cmdMenu.add_separator()
        cmdMenu.add_command(label="Quit", command=reactor.crash)


class TkTwistdFrame(Tkinter.Frame):
    def __init__(self, master, filename = ''):
        Tkinter.Frame.__init__(self, master)

        self.options = twistd.ServerOptions()
        type = tapconvert.guessType(filename)
                              # XXXXXXXXXXXXX
        if type == 'pickle':  # XXXXXXXXXXXXX
            type = 'file'     # XXXXXXXXXXXXX Gah!
                              # XXXXXXXXXXXXX
        self.options[type] = filename
        self.config = tkmktap.TkConfigFrame(self, self.options)
        self.config.pack()
    

    def launch(self):
        self.config.updateConfig(self.options)
        twistd.runApp(self.options)
        tkMessageBox.showinfo(title="Twisted Daemon", message="Daemon Started")
        self.withdraw()


    def destroy(self):
        reactor.crash()


def pickOptions(master, filename):
    config = TkTwistdFrame(master, filename)
    menu = TkTwistdMenu(master, config.launch)
    master['menu'] = menu
    config.pack()


def run():
    r = Tkinter.Tk()
    r.withdraw()
    tksupport.install(r)
    
    filename = tkFileDialog.askopenfilename(
        parent=r, title="Select Twisted APplication File",
        filetypes=FILE_TYPES
    )
    
    working = tkFileDialog.askdirectory(
        parent=r, title="Select Working Directory"
    )
    
    os.chdir(working)
    
    pickOptions(r, filename)

    from twisted.copyright import version
    r.title('Twisted Daemon Launcher ' + version)
    r.deiconify()
    reactor.run()

if __name__ == '__main__':
    run()
