# -*- coding: Latin-1 -*-

"""
This is a compatibility hack to turn twisted.python.usage.Options subclasses
into optparse.OptionParser instances.
"""

from optparse import BadOptionError as UsageError
from optparse import OptionParser, Option

class CompatibilityWrapper(OptionParser):
    def parseArgs(self, args):
        return self.parse_args(args)
    def __getitem__(self, name):
        return getattr(self.values, name)
    def __setitem__(self, name, value):
        setattr(self.values, name, value)
    def __delitem__(self, name):
        delattr(self.values, name)

class HijackOptions(type):
    def __new__(klass, name, bases, attrs):
        opts = {}
        klass.snagFlags(attrs.get('optFlags', ()), opts)
        klass.snagParams(attrs.get('optParameters', ()), opts)
        klass.snagCallbacks(attrs, opts)
        opts = klass.condense(opts)
        parser = CompatibilityWrapper(attrs.get('synopsis'), opts)
        newAttrs = {'parser': parser}
        if '__init__' in attrs:
            newAttrs['__init__'] = attrs['__init__']
        return type.__new__(klass, name, (), newAttrs)

    def __call__(self):
        return self.parser

    def snagFlags(optFlags, opts):
        for (long, short, descr) in optFlags:
            args = []
            if short:
                args.append('-' + short)
            if long:
                args.append('--' + long)
            o = Option(default=0, action="store_true", help=descr, *args)
            if short:
                opts.setdefault(short, []).append(o)
            elif long:
                opts.setdefault(long, []).append(o)
    snagFlags = staticmethod(snagFlags)

    def snagParams(optParameters, opts):
        for (long, short, default, descr) in optParameters:
            args = []
            if short:
                args.append('-' + short)
            if long:
                args.append('--' + long)
            o = Option(default=default, help=descr, dest=long, *args)
            if short:
                opts.setdefault(short, []).append(o)
            elif long:
                opts.setdefault(long, []).append(o)
    snagParams = staticmethod(snagParams)

    def snagCallbacks(attrs, opts):
        def wrap(attrs, name, passValue):
            def wrapped(option, opt, value, parser):
                if passValue:
                    return attrs[name](parser, value)
                else:
                    return attrs[name](parser)
            return wrapped
        for name in attrs:
            if name.startswith('opt_'):
                f = wrap(attrs, name, attrs[name].func_code.co_argcount != 1)
                name = name[4:]
                if len(name) == 1:
                    name = '-' + name
                else:
                    name = '--' + name
                o = Option(name, action="callback", callback=f)
                opts.setdefault(name, []).append(o)
    snagCallbacks = staticmethod(snagCallbacks)

    def condense(opts):
        finalOpts = []
        for (name, options) in opts.items():
            finalOpts.append(options[0])
            for o in options[1:]:
                if o.default is not None:
                    finalOpts[-1].default = o.default
                if o.callback is not None:
                    finalOpts[-1].callback = o.callback
                if o.help is not None:
                    finalOpts[-1].help = o.help
                if o.dest is not None:
                    finalOpts[-1].dest = o.dest
                finalOpts[-1]._short_opts.extend(o._short_opts)
                finalOpts[-1]._long_opts.extend(o._long_opts)

        return finalOpts
    condense = staticmethod(condense)

class Options(object):
    __metaclass__ = HijackOptions
    
    def __init__(self):
        pass

from twisted.python import usage
usage.Options = Options
