"""C++/Twisted integration."""

# make sure fusion._fusion is loaded in a way other C++ code can use it.
import sys
try:
    import dl
    RTLD_NOW = dl.RTLD_NOW
    RTLD_GLOBAL = dl.RTLD_GLOBAL
except ImportError:
    RTLD_NOW = 2
    RTLD_GLOBAL = 256

oldflags = sys.getdlopenflags()
sys.setdlopenflags(RTLD_NOW | RTLD_GLOBAL)
from fusion import _fusion
sys.setdlopenflags(oldflags)

__version__ = "0.1.2-post"
