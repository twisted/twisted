#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
A very simple twisted.words.im-based logbot.

To run the script:
$ python minchat.py
"""


from twisted.words.im import basechat, baseaccount, ircsupport


# A list of account objects. We might as well create them at runtime, this is
# supposed to be a Minimalist Implementation, after all.

accounts = [
    ircsupport.IRCAccount(
        "IRC",
        1,
        "Tooty",  # nickname
        "",  # passwd
        "irc.freenode.net",  # irc server
        6667,  # port
        "#twisted",  # comma-separated list of channels
    )
]


class AccountManager(baseaccount.AccountManager):
    """
    This class is a minimal implementation of the Account Manager.

    Most implementations will show some screen that lets the user add and
    remove accounts, but we're not quite that sophisticated.
    """

    def __init__(self):

        self.chatui = MinChat()

        if len(accounts) == 0:
            print("You have defined no accounts.")
        for acct in accounts:
            acct.logOn(self.chatui)


class MinConversation(basechat.Conversation):
    """
    This class is a minimal implementation of the abstract Conversation class.

    This is all you need to override to receive one-on-one messages.
    """

    def show(self):
        """
        If you don't have a GUI, this is a no-op.
        """
        pass

    def hide(self):
        """
        If you don't have a GUI, this is a no-op.
        """
        pass

    def showMessage(self, text, metadata=None):
        print(f"<{self.person.name}> {text}")

    def contactChangedNick(self, person, newnick):
        basechat.Conversation.contactChangedNick(self, person, newnick)
        print(f"-!- {person.name} is now known as {newnick}")


class MinGroupConversation(basechat.GroupConversation):
    """
    This class is a minimal implementation of the abstract GroupConversation class.

    This is all you need to override to listen in on a group conversation.
    """

    def show(self):
        """
        If you don't have a GUI, this is a no-op.
        """
        pass

    def hide(self):
        """
        If you don't have a GUI, this is a no-op.
        """
        pass

    def showGroupMessage(self, sender, text, metadata=None):
        print(f"<{sender}/{self.group.name}> {text}")

    def setTopic(self, topic, author):
        print(f"-!- {author} set the topic of {self.group.name} to: {topic}")

    def memberJoined(self, member):
        basechat.GroupConversation.memberJoined(self, member)
        print(f"-!- {member} joined {self.group.name}")

    def memberChangedNick(self, oldnick, newnick):
        basechat.GroupConversation.memberChangedNick(self, oldnick, newnick)
        print(f"-!- {oldnick} is now known as {newnick} in {self.group.name}")

    def memberLeft(self, member):
        basechat.GroupConversation.memberLeft(self, member)
        print(f"-!- {member} left {self.group.name}")


class MinChat(basechat.ChatUI):
    """
    This class is a minimal implementation of the abstract ChatUI class.

    There are only two methods that need overriding - and of those two,
    the only change that needs to be made is the default value of the Class
    parameter.
    """

    def getGroupConversation(self, group, Class=MinGroupConversation, stayHidden=0):

        return basechat.ChatUI.getGroupConversation(self, group, Class, stayHidden)

    def getConversation(self, person, Class=MinConversation, stayHidden=0):

        return basechat.ChatUI.getConversation(self, person, Class, stayHidden)


if __name__ == "__main__":
    from twisted.internet import reactor

    AccountManager()

    reactor.run()
