
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

"""I am a test application for twisted.web.
"""

# Sibling Imports
import widgets

# System Imports
import cStringIO
StringIO = cStringIO
del cStringIO


class FunkyForm(widgets.Form):
    formFields = [
        ['string', 'Title', 'title', 'Chicken Little', 'This is for chickens!'],
        ['checkbox', 'First Checkbox', 'checkone', 1],
        ['checkbox', 'Second Checkbox', 'checktwo', 0],
        ['checkgroup', 'First Checkgroup', 'checkn',
         [['zero', "Count Zero", 0],
          ['one', "Count One", 1],
          ['two', "Count Two", 0]]],
        ['menu', 'My Menu', 'mnu',
         [['IDENTIFIER', 'Some Innocuous String'],
          ['TEST_FORM', 'Just another silly string.'],
          ['CONEHEADS', 'Hoo ha.']], 'A menu of stuffs.'],
        ['text', 'Description', 'desc', "Once upon a time..."]
        ]
    submitNames = [
        'Get Funky', 'Get *VERY* Funky'
        ]


class Test(widgets.Gadget, widgets.Presentation):
    """I am a trivial example of a 'web application'.
    """
    template = '''
    Congratulations, twisted.web appears to work!
    <ul>
    <li>Funky Form:
    %%%%self.funkyForm()%%%%
    <li>Exception Handling:
    %%%%self.raiseHell()%%%%
    </ul>
    '''

    def __init__(self):
        """Initialize.
        """
        widgets.Gadget.__init__(self)
        widgets.Presentation.__init__(self)

    funkyForm = FunkyForm

    def deepest(self):
        # Get ready!!
        raise "Hell", "This exception *is* expected."

    def goDeeper(self):
        print 'one level deeper'
        test = self.funkyForm
        self.deepest()

    def raiseHell(self):
        return 'hi'
        x = 1
        y = 2
        z = "some string"; self.goDeeper()

