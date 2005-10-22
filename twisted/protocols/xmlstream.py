import warnings
warnings.warn("twisted.protocols.xmlstream is DEPRECATED. import twisted.words.xish.xmlstream instead.",
              DeprecationWarning, stacklevel=2)

from twisted.words.xish.xmlstream import *
