import warnings
warnings.warn("twisted.runner.procutils is DEPRECATED. import twisted.python.procutils instead.",
              DeprecationWarning, stacklevel=2)

from twisted.python.procutils import which
