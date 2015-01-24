
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using the Twisted IRC Client
============================






A complete howto would explain how to actually use the IRC client.
However, until that howto is written, here is a howto that explains how
to do text formatting for IRC.


    



Text formatting
---------------


    

The text formatting support in Twisted Words is based on the widely used
`mIRC <http://www.mirc.com/>`_ format which supports bold,
underline, reverse video and colored text; nesting these attributes is
also supported.


    



Creating formatted text
~~~~~~~~~~~~~~~~~~~~~~~


    

The API used for creating formatted text in the IRC client is almost the
same as that used by
Twisted :api:`twisted.conch.insults <insults>` .
Text attributes are built up by accessing and indexing attributes on
a special module-level attribute,
:api:`twisted.words.protocols.irc.attributes <twisted.words.protocols.irc.attributes>` ,
multiple values can be passed when indexing attributes to mix text with
nested text attributes. The resulting object can then be serialized to
formatted text, with
:api:`twisted.words.protocols.irc.assembleFormattedText <twisted.words.protocols.irc.assembleFormattedText>` ,
suitable for use with any of the IRC client messaging functions.


    



Bold, underline and reverse video attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    

Bold, underline and reverse video attributes are just flags and are the
simplest text attributes to apply. They are accessed by the names
``bold`` , ``underline`` and ``reverseVideo`` ,
respectively, on
:api:`twisted.words.protocols.irc.attributes <twisted.words.protocols.irc.attributes>` . For
example, messaging someone the bold and underlined text "Hello world!":



.. code-block:: python

    
    from twisted.words.protocols.irc import assembleFormattedText, attributes as A
    
    # Message "someone" the bold and underlined text "Hello world!"
    anIRCClient.msg('someone', assembleFormattedText(
        A.bold[
            A.underline['Hello world!']])




    



The "normal" attribute
~~~~~~~~~~~~~~~~~~~~~~


    

At first glance a text attribute called "normal" that does not apply any
unusual text attributes may not seem that special but it can be quite
useful, both as a container:



.. code-block:: python

    
    A.normal[
        'This is normal text. ',
        A.bold['This is bold text! '],
        'Back to normal',
        A.underline['This is underlined text!']]



And also as a way to temporarily disable text attributes without having to
close and respecify all text attributes for a brief piece of text:



.. code-block:: python

    
    A.normal[
        A.reverseVideo['This is reverse, ', A.normal['except for this'], ', text']]



It is worth noting that assembled text will always begin with the control
code to disable other attributes for the sake of correctness.


    



Color attributes
~~~~~~~~~~~~~~~~


    

Since colors for both the foreground and background can be specified with
IRC text formatting another level of attribute access is introduced.
Firstly the foreground or background, through the
``fg`` and ``bg`` attribute names respectively, is
accessed and then the color name is accessed. The available color
attribute names are:


    




- white
- black
- blue
- green
- lightRed
- red
- magenta
- orange
- yellow
- lightGreen
- cyan
- lightCyan
- lightBlue
- lightMagenta
- gray
- lightGray


    



It is possible to nest foreground and background colors to alter both
for a single piece of text. For example to display black on green text:



.. code-block:: python

    
    A.fg.black[A.bg.green['Like a terminal!']]




    



Parsing formatted text
~~~~~~~~~~~~~~~~~~~~~~


    

Most IRC clients format text so it is logical that you may want to parse
this formatted text.
:api:`twisted.words.protocols.irc.parseFormattedText <twisted.words.protocols.irc.parseFormattedText>` 
will parse text into structured text attributes. It is worth noting that
while feeding the output of ``parseFormattedText`` back to
``assembleFormattedText`` will produce the same final result,
the actual structure of the parsed text will differ. Color codes are
mapped from 0 to 15, codes greater than 15 will begin to wrap around.


    



Removing formatting
~~~~~~~~~~~~~~~~~~~


    

In some cases, such as an automaton handling user input from IRC, it is
desirable to have all formatting stripped from text. This can be
accomplished with
:api:`twisted.words.protocols.irc.stripFormatting <twisted.words.protocols.irc.stripFormatting>` .

  

