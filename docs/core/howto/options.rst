
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Parsing command-lines with usage.Options
========================================






Introduction
------------


    
There is frequently a need for programs to parse a UNIX-like
command line program: options preceded by ``-`` or
``--`` , sometimes followed by a parameter, followed by
a list of arguments. The :api:`twisted.python.usage <twisted.python.usage>` provides a class,
``Options`` , to facilitate such parsing.

    


While Python has the ``getopt`` module for doing
this, it provides a very low level of abstraction for options.
Twisted has a higher level of abstraction, in the class :api:`twisted.python.usage.Options <twisted.python.usage.Options>` . It uses
Python's reflection facilities to provide an easy to use yet
flexible interface to the command line. While most command line
processors either force the application writer to write their own
loops, or have arbitrary limitations on the command line (the
most common one being not being able to have more than one
instance of a specific option, thus rendering the idiom
``program -v -v -v`` impossible), Twisted allows the
programmer to decide how much control they want.

    


The ``Options`` class is used by subclassing. Since
a lot of time it will be used in the :api:`twisted.tap <twisted.tap>` package, where the local
conventions require the specific options parsing class to also
be called ``Options`` , it is usually imported with




.. code-block:: python

    
    from twisted.python import usage



    

Boolean Options
---------------


    
For simple boolean options, define the attribute
``optFlags`` like this:




.. code-block:: python

    
    class Options(usage.Options):
    
        optFlags = [["fast", "f", "Act quickly"], ["safe", "s", "Act safely"]]


    
``optFlags`` should be a list of 3-lists. The first element
is the long name, and will be used on the command line as
``--fast`` . The second one is the short name, and will be used
on the command line as ``-f`` . The last element is a
description of the flag and will be used to generate the usage
information text.  The long name also determines the name of the key
that will be set on the Options instance. Its value will be 1 if the
option was seen, 0 otherwise. Here is an example for usage:




.. code-block:: python

    
    class Options(usage.Options):
    
        optFlags = [
            ["fast", "f", "Act quickly"],
            ["good", "g", "Act well"],
            ["cheap", "c", "Act cheaply"]
        ]
    
    command_line = ["-g", "--fast"]
    
    options = Options()
    try:
        options.parseOptions(command_line)
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    if options['fast']:
        print "fast",
    if options['good']:
        print "good",
    if options['cheap']:
        print "cheap",
    print



    
The above will print ``fast good`` .

    


Note here that Options fully supports the mapping interface. You can
access it mostly just like you can access any other dict. Options are stored
as mapping items in the Options instance: parameters as 'paramname': 'value'
and flags as 'flagname': 1 or 0.


Inheritance, Or: How I Learned to Stop Worrying and Love the Superclass
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes there is a need for several option processors with a unifying core.
Perhaps you want all your commands to understand ``-q`` /``--quiet`` means to be quiet, or something similar.
On the face of it, this looks impossible: in Python, the subclass's ``optFlags`` would shadow the superclass's.
However, ``usage.Options`` uses special reflection code to get all of the ``optFlags`` defined in the hierarchy. So the following:

.. code-block:: python

    class BaseOptions(usage.Options):

        optFlags = [["quiet", "q", None]]

    class SpecificOptions(BaseOptions):

        optFlags = [
            ["fast", "f", None], ["good", "g", None], ["cheap", "c", None]
        ]

Is the same as:

.. code-block:: python

    class SpecificOptions(usage.Options):

        optFlags = [
            ["quiet", "q", "Silence output"],
            ["fast", "f", "Run quickly"],
            ["good", "g", "Don't validate input"],
            ["cheap", "c", "Use cheap resources"]
        ]


Parameters
----------

Parameters are specified using the attribute
``optParameters`` . They *must* be given a
default. If you want to make sure you got the parameter from
the command line, give a non-string default. Since the command
line only has strings, this is completely reliable.

    


Here is an example:




.. code-block:: python

    
    from twisted.python import usage
    
    class Options(usage.Options):
    
        optFlags = [
            ["fast", "f", "Run quickly"],
            ["good", "g", "Don't validate input"],
            ["cheap", "c", "Use cheap resources"]
        ]
        optParameters = [["user", "u", None, "The user name"]]
    
    config = Options()
    try:
        config.parseOptions() # When given no argument, parses sys.argv[1:]
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    
    if config['user'] is not None:
        print "Hello", config['user']
    print "So, you want it:"
    
    if config['fast']:
        print "fast",
    if config['good']:
        print "good",
    if config['cheap']:
        print "cheap",
    print



    
Like ``optFlags`` , ``optParameters`` works
smoothly with inheritance.

    



Option Subcommands
------------------


    
It is useful, on occasion, to group a set of options together based
on the logical "action" to which they belong.  For this, the
``usage.Options`` class allows you to define a set of
"subcommands" , each of which can provide its own
``usage.Options`` instance to handle its particular
options.

    


Here is an example for an Options class that might parse
options like those the cvs program takes




.. code-block:: python

    
    from twisted.python import usage
    
    class ImportOptions(usage.Options):
        optParameters = [
            ['module', 'm', None, None], ['vendor', 'v', None, None],
            ['release', 'r', None]
        ]
    
    class CheckoutOptions(usage.Options):
        optParameters = [['module', 'm', None, None], ['tag', 'r', None, None]]
    
    class Options(usage.Options):
        subCommands = [['import', None, ImportOptions, "Do an Import"],
                       ['checkout', None, CheckoutOptions, "Do a Checkout"]]
    
        optParameters = [
            ['compression', 'z', 0, 'Use compression'],
            ['repository', 'r', None, 'Specify an alternate repository']
        ]
    
    config = Options(); config.parseOptions()
    if config.subCommand == 'import':
        doImport(config.subOptions)
    elif config.subCommand == 'checkout':
        doCheckout(config.subOptions)



    
The ``subCommands`` attribute of ``Options`` 
directs the parser to the two other ``Options`` subclasses
when the strings ``"import"`` or ``"checkout"`` are
present on the command
line.  All options after the given command string are passed to the
specified Options subclass for further parsing.  Only one subcommand
may be specified at a time.  After parsing has completed, the Options
instance has two new attributes - ``subCommand`` and ``subOptions`` - which hold the command string and the Options
instance used to parse the remaining options.

    



Generic Code For Options
------------------------


    
Sometimes, just setting an attribute on the basis of the
options is not flexible enough. In those cases, Twisted does
not even attempt to provide abstractions such as "counts" or
"lists" , but rather lets you call your own method, which will
be called whenever the option is encountered.

    


Here is an example of counting verbosity




.. code-block:: python

    
    from twisted.python import usage
    
    class Options(usage.Options):
    
        def __init__(self):
            usage.Options.__init__(self)
            self['verbosity'] = 0 # default
    
        def opt_verbose(self):
            self['verbosity'] = self['verbosity']+1
    
        def opt_quiet(self):
            self['verbosity'] = self['verbosity']-1
    
        opt_v = opt_verbose
        opt_q = opt_quiet



    
Command lines that look like
``command -v -v -v -v`` will
increase verbosity to 4, while
``command -q -q -q`` will decrease
verbosity to -3.


    


The :api:`twisted.python.usage.Options <usage.Options>` 
class knows that these are
parameter-less options, since the methods do not receive an
argument. Here is an example for a method with a parameter:





.. code-block:: python

    
    from twisted.python import usage
    
    class Options(usage.Options):
    
        def __init__(self):
            usage.Options.__init__(self)
            self['symbols'] = []
    
        def opt_define(self, symbol):
            self['symbols'].append(symbol)
    
        opt_D = opt_define



    
This example is useful for the common idiom of having
``command -DFOO -DBAR`` to define symbols.

    



Parsing Arguments
-----------------


    
``usage.Options`` does not stop helping when the
last parameter is gone. All the other arguments are sent into a
function which should deal with them. Here is an example for a
``cmp`` like command.




.. code-block:: python

    
    from twisted.python import usage
    
    class Options(usage.Options):
    
        optParameters = [["max_differences", "d", 1, None]]
    
        def parseArgs(self, origin, changed):
            self['origin'] = origin
            self['changed'] = changed



    
The command should look like ``command origin changed`` .

    


If you want to have a variable number of left-over
arguments, just use ``def parseArgs(self, *args):`` .
This is useful for commands like the UNIX
``cat(1)`` .

    



Post Processing
---------------


    
Sometimes, you want to perform post processing of options to
patch up inconsistencies, and the like. Here is an example:




.. code-block:: python

    
    from twisted.python import usage
    
    class Options(usage.Options):
    
        optFlags = [
            ["fast", "f", "Run quickly"],
            ["good", "g", "Don't validate input"],
            ["cheap", "c", "Use cheap resources"]
        ]
    
        def postOptions(self):
            if self['fast'] and self['good'] and self['cheap']:
                raise usage.UsageError, "can't have it all, brother"



    

Type enforcement
----------------


    
By default, all options are handled as strings. You may want to
enforce the type of your option in some specific case, the classic example
being port number. Any callable can be specified in the fifth row of
``optParameters`` and will be called with the string value passed
in parameter.






.. code-block:: python

    
    from twisted.python import usage
    
    class Options(usage.Options):
        optParameters = [
                ["shiny_integer", "s", 1, None, int],
                ["dummy_float", "d", 3.14159, None, float],
            ]



    
Note that default values are not coerced, so you should either declare
it with the good type (as above) or handle it when you use your
options.

    


The coerce function may have a coerceDoc attribute, the content of which
will be printed after the documentation of the option. It's particularly
useful for reusing the function at multiple places.





.. code-block:: python

    
    def oneTwoThree(val):
        val = int(val)
        if val not in range(1, 4):
            raise ValueError("Not in range")
        return val
    oneTwoThree.coerceDoc = "Must be 1, 2 or 3."
    
    from twisted.python import usage
    
    class Options(usage.Options):
        optParameters = [["one_choice", "o", 1, None, oneTwoThree]]




This example code will print the following help when added to your program:





.. code-block:: console

    
    $ python myprogram.py --help
    Usage: myprogram [options] 
    Options:
      -o, --one_choice=           [default: 0]. Must be 1, 2 or 3.


    

Shell tab-completion
--------------------


    
The ``Options`` class may provide tab-completion to interactive
command shells. Only ``zsh`` is supported at present, but there is 
some interest in supporting ``bash`` in the future.

    


Support is automatic for all of the commands shipped with Twisted. Zsh
has shipped, for a number of years, a completion function which ties in to
the support provided by the ``Options`` class.

    


If you are writing a ``twistd`` plugin, then tab-completion
for your ``twistd`` sub-command is also automatic.

    


For other commands you may easily provide zsh tab-completion support.
Copy the file "twisted/python/twisted-completion.zsh" and name it something
like "_mycommand". A leading underscore with no extension is zsh's
convention for completion function files.

    


Edit the new file and change the first line to refer only to your new
command(s), like so:





.. code-block:: console

    
    #compdef mycommand


    
    
Then ensure this file is made available to the shell by placing it in
one of the directories appearing in zsh's $fpath. Restart zsh, and ensure
advanced completion is enabled
(``autoload -U compinit; compinit)`` . You should then be able to
type the name of your command and press Tab to have your command-line
options completed.

    



Completion metadata
~~~~~~~~~~~~~~~~~~~


    
Optionally, a special attribute, ``compData`` , may be defined
on your ``Options`` subclass in order to provide more information
to the shell-completion system. The attribute should be an instance of
I DON'T KNOW WHAT TO DO WITH THIS LINK!

    


In addition, ``compData`` may be defined on parent classes in
your inheritance hiearchy. The information from each
I DON'T KNOW WHAT TO DO WITH THIS LINK!
  

