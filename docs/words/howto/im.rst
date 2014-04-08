
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Overview of Twisted IM
======================





Twisted IM (Instance Messenger) is a multi-protocol chat
framework, based on the Twisted framework we've all come to know
and love. It's fairly simple and extensible in two directions -
it's pretty easy to add new protocols, and it's also quite easy
to add new front-ends.

		



Code flow
---------


		

AccountManager
~~~~~~~~~~~~~~

		
The control flow starts at the relevant subclass of :api:`twisted.words.im.baseaccount.AccountManager <baseaccount.AccountManager>` .
The AccountManager is responsible for, well, managing accounts
- remembering what accounts are available, their
settings, adding and removal of accounts, and making accounts
log on at startup.

		


This would be a good place to start your interface, load a
list of accounts from disk and tell them to login. Most of the
method names in :api:`twisted.words.im.baseaccount.AccountManager <AccountManager>` 
are pretty self-explanatory, and your subclass can override
whatever it wants, but you *need* to override ``__init__`` . Something like
this:

		



.. code-block:: python

    
    ...
        def __init__(self):
            self.chatui = ... # Your subclass of basechat.ChatUI
            self.accounts = ... # Load account list
            for a in self.accounts:
                a.logOn(self.chatui)



		

ChatUI
~~~~~~

		
Account objects talk to the user via a subclass of :api:`twisted.words.im.basechat.ChatUI <basechat.ChatUI>` .
This class keeps track of all the various conversations that
are currently active, so that when an account receives and
incoming message, it can put that message in its correct
context.

		


How much of this class you need to override depends on what
you need to do. You will need to override
``getConversation`` (a one-on-one conversation, like
an IRC DCC chat) and ``getGroupConversation`` (a
multiple user conversation, like an IRC channel). You might
want to override ``getGroup`` and
``getPerson`` .

		


The main problem with the default versions of the above
routines is that they take a parameter, ``Class`` ,
which defaults to an abstract implementation of that class -
for example, ``getConversation`` has a
``Class`` parameter that defaults to :api:`twisted.words.im.basechat.Conversation <basechat.Conversation>` which
raises a lot of ``NotImplementedError`` s. In your
subclass, override the method with a new method whose Class
parameter defaults to your own implementation of
``Conversation`` , that simply calls the parent
class' implementation.

		



Conversation and GroupConversation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

		
These classes are where your interface meets the chat
protocol. Chat protocols get a message, find the appropriate
``Conversation`` or ``GroupConversation`` 
object, and call its methods when various interesting things
happen.

		


Override whatever methods you want to get the information
you want to display. You must override the ``hide`` 
and ``show`` methods, however - they are called
frequently and the default implementation raises
``NotImplementedError`` .

		



Accounts
~~~~~~~~

		
An account is an instance of a subclass of :api:`twisted.words.im.basesupport.AbstractAccount <basesupport.AbstractAccount>` .
For more details and sample code, see the various
``*support`` files in ``twisted.words.im`` .

	

