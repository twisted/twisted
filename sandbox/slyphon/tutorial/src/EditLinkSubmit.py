from twisted.web.microdom import lmx
from twisted.web.woven.widgets import KeyedList
from twisted.web.woven.model import StringModel

from SuperPage import SuperPage
from SuperPage import Option

import Constant

import dbcnx
import pdb

class EditLinkSubmit(SuperPage):
    def __init__(self, *args, **kwargs):
        SuperPage.__init__(self, *args, **kwargs)
        self.template = '<html></html>'
        kwargs['request'].redirect('/home')

