import warnings
try:
    from event_libevent import *
except ImportError:
    from event_compat import *
    warnings.warn("using event_compat instead of suggested event_libevent (will impact performance)")

