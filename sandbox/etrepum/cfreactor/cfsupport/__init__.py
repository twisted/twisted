import cfsupport._cfsocketmanager
import objc
from CoreFoundation import *

CFSocketManager = objc.lookUpClass('CFSocketManager')
CFSocketDelegate = objc.lookUpClass('CFSocketDelegate')

