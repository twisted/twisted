
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Internet Relay Chat Protocol implementation
"""

from twisted.protocols import basic, protocol
from twisted.python import log
import string

class IRCParseError(ValueError):
    pass

def parsemsg(s):
    prefix = ''
    trailing = []
    if s[0] == ':':
        prefix, s = string.split(s[1:], ' ', 1)
    if string.find(s,':') != -1:
        s, trailing = string.split(s, ':', 1)
        args = string.split(s)
        args.append(trailing)
    else:
        args = string.split(s)
    command = args.pop(0)
    return prefix, command, args


class IRC(protocol.Protocol):
    buffer = ""

    def connectionMade(self):
        log.msg("irc connection made")
        self.channels = []

    def sendLine(self, line):
        self.transport.write(line+"\r\n")

    def sendMessage(self, command, *parameter_list, **prefix):
        """Send a line formatted as an IRC message.

        First argument is the command, all subsequent arguments
        are parameters to that command.  If a prefix is desired,
        it may be specified with the keyword argument 'prefix'.
        """

        if not command:
            raise ValueError, "IRC message requires a command."

        if ' ' in command or command[0] == ':':
            # Not the ONLY way to screw up, but provides a little
            # sanity checking to catch likely dumb mistakes.
            raise ValueError, "Somebody screwed up, 'cuz this doesn't" \
                  " look like a command to me: %s" % command

        line = string.join([command] + list(parameter_list))
        if prefix.has_key('prefix'):
            line = ":%s %s" % (prefix['prefix'], line)
        self.sendLine(line)

        if len(parameter_list) > 15:
            warn("Message has %d parameters (RFC allows 15):\n%s" %
                 len(parameter_list), line)

    def dataReceived(self, data):
        """ This hack is to support mIRC, which sends LF only, even though the
        RFC says CRLF.  (Also, the flexibility of LineReceiver to turn "line
        mode" on and off was not required.)
        """
        self.buffer = self.buffer + data
        lines = string.split(self.buffer, "\n") # get the lines
        self.buffer = lines.pop() # pop the last element (we're not sure it's a line)
        for line in lines:
            if len(line) <= 2:
                # This is a blank line, at best.
                continue
            if line[-1] == "\r":
                line = line[:-1]
            prefix, command, params = parsemsg(line)
            # MIRC is a big pile of doo-doo
            command = string.upper(command)
            log.msg( "%s %s %s" % (prefix, command, params))
            method = getattr(self, "irc_%s" % command, None)
            if method is not None:
                method(prefix, params)
            else:
                self.irc_unknown(prefix, command, params)

class IRCClient(basic.LineReceiver):

    def join(self, channel):
        self.sendLine("JOIN #%s" % channel)

    def leave(self, channel):
        self.sendLine("PART #%s" % channel)

    def say(self, channel, message):
        self.sendLine("PRIVMSG #%s :%s" % (channel, message))

    def msg(self, user, message):
        self.sendLine("PRIVMSG %s :%s" % (user, message))

    def notice(self, user, message):
        self.sendLine("NOTICE %s :%s" % (user, message))

    def away(self, message=''):
        self.sendLine("AWAY :%s" % message)

    def setNick(self, nickname):
        self.nickname = nickname
        self.sendLine("NICK %s" % nickname)

    def irc_443(self, prefix, params):
        self.setNick(self.nickname+'_')

    def irc_JOIN(self, prefix, params):
        pass

    def irc_PING(self, prefix, params):
        self.sendLine("PONG %s" % params[-1])

    def irc_PRIVMSG(self, prefix, params):
        user = prefix
        channel = params[0]
        message = params[-1]
        if message[0]=="\001":
            if message[1:5]=="PING":
                self.notice(string.split(user,"!")[0],"\001PING "+message[6:])
                return
        self.privmsg(user, channel, message)

    irc_NOTICE = irc_PRIVMSG

    def privmsg(self, user, channel, message):
        pass

    def irc_unknown(self, prefix, command, params):
        pass

    def lineReceived(self, line):
        prefix, command, params = parsemsg(line)
        method = getattr(self, "irc_%s" % command, None)
        if method is not None:
            method(prefix, params)
        else:
            self.irc_unknown(prefix, command, params)

# Constants (from RFC 2812)
RPL_WELCOME = '001'
RPL_YOURHOST = '002'
RPL_CREATED = '003'
RPL_MYINFO = '004'
RPL_BOUNCE = '005'
RPL_USERHOST = '302'
RPL_ISON = '303'
RPL_AWAY = '301'
RPL_UNAWAY = '305'
RPL_NOWAWAY = '306'
RPL_WHOISUSER = '311'
RPL_WHOISSERVER = '312'
RPL_WHOISOPERATOR = '313'
RPL_WHOISIDLE = '317'
RPL_ENDOFWHOIS = '318'
RPL_WHOISCHANNELS = '319'
RPL_WHOWASUSER = '314'
RPL_ENDOFWHOWAS = '369'
RPL_LISTSTART = '321'
RPL_LIST = '322'
RPL_LISTEND = '323'
RPL_UNIQOPIS = '325'
RPL_CHANNELMODEIS = '324'
RPL_NOTOPIC = '331'
RPL_TOPIC = '332'
RPL_INVITING = '341'
RPL_SUMMONING = '342'
RPL_INVITELIST = '346'
RPL_ENDOFINVITELIST = '347'
RPL_EXCEPTLIST = '348'
RPL_ENDOFEXCEPTLIST = '349'
RPL_VERSION = '351'
RPL_WHOREPLY = '352'
RPL_ENDOFWHO = '315'
RPL_NAMREPLY = '353'
RPL_ENDOFNAMES = '366'
RPL_LINKS = '364'
RPL_ENDOFLINKS = '365'
RPL_BANLIST = '367'
RPL_ENDOFBANLIST = '368'
RPL_INFO = '371'
RPL_ENDOFINFO = '374'
RPL_MOTDSTART = '375'
RPL_MOTD = '372'
RPL_ENDOFMOTD = '376'
RPL_YOUREOPER = '381'
RPL_REHASHING = '382'
RPL_YOURESERVICE = '383'
RPL_TIME = '391'
RPL_USERSSTART = '392'
RPL_USERS = '393'
RPL_ENDOFUSERS = '394'
RPL_NOUSERS = '395'
RPL_TRACELINK = '200'
RPL_TRACECONNECTING = '201'
RPL_TRACEHANDSHAKE = '202'
RPL_TRACEUNKNOWN = '203'
RPL_TRACEOPERATOR = '204'
RPL_TRACEUSER = '205'
RPL_TRACESERVER = '206'
RPL_TRACESERVICE = '207'
RPL_TRACENEWTYPE = '208'
RPL_TRACECLASS = '209'
RPL_TRACERECONNECT = '210'
RPL_TRACELOG = '261'
RPL_TRACEEND = '262'
RPL_STATSLINKINFO = '211'
RPL_STATSCOMMANDS = '212'
RPL_ENDOFSTATS = '219'
RPL_STATSUPTIME = '242'
RPL_STATSOLINE = '243'
RPL_UMODEIS = '221'
RPL_SERVLIST = '234'
RPL_SERVLISTEND = '235'
RPL_LUSERCLIENT = '251'
RPL_LUSEROP = '252'
RPL_LUSERUNKNOWN = '253'
RPL_LUSERCHANNELS = '254'
RPL_LUSERME = '255'
RPL_ADMINME = '256'
RPL_ADMINLOC = '257'
RPL_ADMINLOC = '258'
RPL_ADMINEMAIL = '259'
RPL_TRYAGAIN = '263'
ERR_NOSUCHNICK = '401'
ERR_NOSUCHSERVER = '402'
ERR_NOSUCHCHANNEL = '403'
ERR_CANNOTSENDTOCHAN = '404'
ERR_TOOMANYCHANNELS = '405'
ERR_WASNOSUCHNICK = '406'
ERR_TOOMANYTARGETS = '407'
ERR_NOSUCHSERVICE = '408'
ERR_NOORIGIN = '409'
ERR_NORECIPIENT = '411'
ERR_NOTEXTTOSEND = '412'
ERR_NOTOPLEVEL = '413'
ERR_WILDTOPLEVEL = '414'
ERR_BADMASK = '415'
ERR_UNKNOWNCOMMAND = '421'
ERR_NOMOTD = '422'
ERR_NOADMININFO = '423'
ERR_FILEERROR = '424'
ERR_NONICKNAMEGIVEN = '431'
ERR_ERRONEUSNICKNAME = '432'
ERR_NICKNAMEINUSE = '433'
ERR_NICKCOLLISION = '436'
ERR_UNAVAILRESOURCE = '437'
ERR_USERNOTINCHANNEL = '441'
ERR_NOTONCHANNEL = '442'
ERR_USERONCHANNEL = '443'
ERR_NOLOGIN = '444'
ERR_SUMMONDISABLED = '445'
ERR_USERSDISABLED = '446'
ERR_NOTREGISTERED = '451'
ERR_NEEDMOREPARAMS = '461'
ERR_ALREADYREGISTRED = '462'
ERR_NOPERMFORHOST = '463'
ERR_PASSWDMISMATCH = '464'
ERR_YOUREBANNEDCREEP = '465'
ERR_YOUWILLBEBANNED = '466'
ERR_KEYSET = '467'
ERR_CHANNELISFULL = '471'
ERR_UNKNOWNMODE = '472'
ERR_INVITEONLYCHAN = '473'
ERR_BANNEDFROMCHAN = '474'
ERR_BADCHANNELKEY = '475'
ERR_BADCHANMASK = '476'
ERR_NOCHANMODES = '477'
ERR_BANLISTFULL = '478'
ERR_NOPRIVILEGES = '481'
ERR_CHANOPRIVSNEEDED = '482'
ERR_CANTKILLSERVER = '483'
ERR_RESTRICTED = '484'
ERR_UNIQOPPRIVSNEEDED = '485'
ERR_NOOPERHOST = '491'
ERR_UMODEUNKNOWNFLAG = '501'
ERR_USERSDONTMATCH = '502'

# And hey, as long as the strings are already intern'd...
symbolic_to_numeric = {
    "RPL_WELCOME": '001',
    "RPL_YOURHOST": '002',
    "RPL_CREATED": '003',
    "RPL_MYINFO": '004',
    "RPL_BOUNCE": '005',
    "RPL_USERHOST": '302',
    "RPL_ISON": '303',
    "RPL_AWAY": '301',
    "RPL_UNAWAY": '305',
    "RPL_NOWAWAY": '306',
    "RPL_WHOISUSER": '311',
    "RPL_WHOISSERVER": '312',
    "RPL_WHOISOPERATOR": '313',
    "RPL_WHOISIDLE": '317',
    "RPL_ENDOFWHOIS": '318',
    "RPL_WHOISCHANNELS": '319',
    "RPL_WHOWASUSER": '314',
    "RPL_ENDOFWHOWAS": '369',
    "RPL_LISTSTART": '321',
    "RPL_LIST": '322',
    "RPL_LISTEND": '323',
    "RPL_UNIQOPIS": '325',
    "RPL_CHANNELMODEIS": '324',
    "RPL_NOTOPIC": '331',
    "RPL_TOPIC": '332',
    "RPL_INVITING": '341',
    "RPL_SUMMONING": '342',
    "RPL_INVITELIST": '346',
    "RPL_ENDOFINVITELIST": '347',
    "RPL_EXCEPTLIST": '348',
    "RPL_ENDOFEXCEPTLIST": '349',
    "RPL_VERSION": '351',
    "RPL_WHOREPLY": '352',
    "RPL_ENDOFWHO": '315',
    "RPL_NAMREPLY": '353',
    "RPL_ENDOFNAMES": '366',
    "RPL_LINKS": '364',
    "RPL_ENDOFLINKS": '365',
    "RPL_BANLIST": '367',
    "RPL_ENDOFBANLIST": '368',
    "RPL_INFO": '371',
    "RPL_ENDOFINFO": '374',
    "RPL_MOTDSTART": '375',
    "RPL_MOTD": '372',
    "RPL_ENDOFMOTD": '376',
    "RPL_YOUREOPER": '381',
    "RPL_REHASHING": '382',
    "RPL_YOURESERVICE": '383',
    "RPL_TIME": '391',
    "RPL_USERSSTART": '392',
    "RPL_USERS": '393',
    "RPL_ENDOFUSERS": '394',
    "RPL_NOUSERS": '395',
    "RPL_TRACELINK": '200',
    "RPL_TRACECONNECTING": '201',
    "RPL_TRACEHANDSHAKE": '202',
    "RPL_TRACEUNKNOWN": '203',
    "RPL_TRACEOPERATOR": '204',
    "RPL_TRACEUSER": '205',
    "RPL_TRACESERVER": '206',
    "RPL_TRACESERVICE": '207',
    "RPL_TRACENEWTYPE": '208',
    "RPL_TRACECLASS": '209',
    "RPL_TRACERECONNECT": '210',
    "RPL_TRACELOG": '261',
    "RPL_TRACEEND": '262',
    "RPL_STATSLINKINFO": '211',
    "RPL_STATSCOMMANDS": '212',
    "RPL_ENDOFSTATS": '219',
    "RPL_STATSUPTIME": '242',
    "RPL_STATSOLINE": '243',
    "RPL_UMODEIS": '221',
    "RPL_SERVLIST": '234',
    "RPL_SERVLISTEND": '235',
    "RPL_LUSERCLIENT": '251',
    "RPL_LUSEROP": '252',
    "RPL_LUSERUNKNOWN": '253',
    "RPL_LUSERCHANNELS": '254',
    "RPL_LUSERME": '255',
    "RPL_ADMINME": '256',
    "RPL_ADMINLOC": '257',
    "RPL_ADMINLOC": '258',
    "RPL_ADMINEMAIL": '259',
    "RPL_TRYAGAIN": '263',
    "ERR_NOSUCHNICK": '401',
    "ERR_NOSUCHSERVER": '402',
    "ERR_NOSUCHCHANNEL": '403',
    "ERR_CANNOTSENDTOCHAN": '404',
    "ERR_TOOMANYCHANNELS": '405',
    "ERR_WASNOSUCHNICK": '406',
    "ERR_TOOMANYTARGETS": '407',
    "ERR_NOSUCHSERVICE": '408',
    "ERR_NOORIGIN": '409',
    "ERR_NORECIPIENT": '411',
    "ERR_NOTEXTTOSEND": '412',
    "ERR_NOTOPLEVEL": '413',
    "ERR_WILDTOPLEVEL": '414',
    "ERR_BADMASK": '415',
    "ERR_UNKNOWNCOMMAND": '421',
    "ERR_NOMOTD": '422',
    "ERR_NOADMININFO": '423',
    "ERR_FILEERROR": '424',
    "ERR_NONICKNAMEGIVEN": '431',
    "ERR_ERRONEUSNICKNAME": '432',
    "ERR_NICKNAMEINUSE": '433',
    "ERR_NICKCOLLISION": '436',
    "ERR_UNAVAILRESOURCE": '437',
    "ERR_USERNOTINCHANNEL": '441',
    "ERR_NOTONCHANNEL": '442',
    "ERR_USERONCHANNEL": '443',
    "ERR_NOLOGIN": '444',
    "ERR_SUMMONDISABLED": '445',
    "ERR_USERSDISABLED": '446',
    "ERR_NOTREGISTERED": '451',
    "ERR_NEEDMOREPARAMS": '461',
    "ERR_ALREADYREGISTRED": '462',
    "ERR_NOPERMFORHOST": '463',
    "ERR_PASSWDMISMATCH": '464',
    "ERR_YOUREBANNEDCREEP": '465',
    "ERR_YOUWILLBEBANNED": '466',
    "ERR_KEYSET": '467',
    "ERR_CHANNELISFULL": '471',
    "ERR_UNKNOWNMODE": '472',
    "ERR_INVITEONLYCHAN": '473',
    "ERR_BANNEDFROMCHAN": '474',
    "ERR_BADCHANNELKEY": '475',
    "ERR_BADCHANMASK": '476',
    "ERR_NOCHANMODES": '477',
    "ERR_BANLISTFULL": '478',
    "ERR_NOPRIVILEGES": '481',
    "ERR_CHANOPRIVSNEEDED": '482',
    "ERR_CANTKILLSERVER": '483',
    "ERR_RESTRICTED": '484',
    "ERR_UNIQOPPRIVSNEEDED": '485',
    "ERR_NOOPERHOST": '491',
    "ERR_UMODEUNKNOWNFLAG": '501',
    "ERR_USERSDONTMATCH": '502',
}

integer_to_symbolic = {
    1: "RPL_WELCOME",
    2: "RPL_YOURHOST",
    3: "RPL_CREATED",
    4: "RPL_MYINFO",
    5: "RPL_BOUNCE",
    302: "RPL_USERHOST",
    303: "RPL_ISON",
    301: "RPL_AWAY",
    305: "RPL_UNAWAY",
    306: "RPL_NOWAWAY",
    311: "RPL_WHOISUSER",
    312: "RPL_WHOISSERVER",
    313: "RPL_WHOISOPERATOR",
    317: "RPL_WHOISIDLE",
    318: "RPL_ENDOFWHOIS",
    319: "RPL_WHOISCHANNELS",
    314: "RPL_WHOWASUSER",
    369: "RPL_ENDOFWHOWAS",
    321: "RPL_LISTSTART",
    322: "RPL_LIST",
    323: "RPL_LISTEND",
    325: "RPL_UNIQOPIS",
    324: "RPL_CHANNELMODEIS",
    331: "RPL_NOTOPIC",
    332: "RPL_TOPIC",
    341: "RPL_INVITING",
    342: "RPL_SUMMONING",
    346: "RPL_INVITELIST",
    347: "RPL_ENDOFINVITELIST",
    348: "RPL_EXCEPTLIST",
    349: "RPL_ENDOFEXCEPTLIST",
    351: "RPL_VERSION",
    352: "RPL_WHOREPLY",
    315: "RPL_ENDOFWHO",
    353: "RPL_NAMREPLY",
    366: "RPL_ENDOFNAMES",
    364: "RPL_LINKS",
    365: "RPL_ENDOFLINKS",
    367: "RPL_BANLIST",
    368: "RPL_ENDOFBANLIST",
    371: "RPL_INFO",
    374: "RPL_ENDOFINFO",
    375: "RPL_MOTDSTART",
    372: "RPL_MOTD",
    376: "RPL_ENDOFMOTD",
    381: "RPL_YOUREOPER",
    382: "RPL_REHASHING",
    383: "RPL_YOURESERVICE",
    391: "RPL_TIME",
    392: "RPL_USERSSTART",
    393: "RPL_USERS",
    394: "RPL_ENDOFUSERS",
    395: "RPL_NOUSERS",
    200: "RPL_TRACELINK",
    201: "RPL_TRACECONNECTING",
    202: "RPL_TRACEHANDSHAKE",
    203: "RPL_TRACEUNKNOWN",
    204: "RPL_TRACEOPERATOR",
    205: "RPL_TRACEUSER",
    206: "RPL_TRACESERVER",
    207: "RPL_TRACESERVICE",
    208: "RPL_TRACENEWTYPE",
    209: "RPL_TRACECLASS",
    210: "RPL_TRACERECONNECT",
    261: "RPL_TRACELOG",
    262: "RPL_TRACEEND",
    211: "RPL_STATSLINKINFO",
    212: "RPL_STATSCOMMANDS",
    219: "RPL_ENDOFSTATS",
    242: "RPL_STATSUPTIME",
    243: "RPL_STATSOLINE",
    221: "RPL_UMODEIS",
    234: "RPL_SERVLIST",
    235: "RPL_SERVLISTEND",
    251: "RPL_LUSERCLIENT",
    252: "RPL_LUSEROP",
    253: "RPL_LUSERUNKNOWN",
    254: "RPL_LUSERCHANNELS",
    255: "RPL_LUSERME",
    256: "RPL_ADMINME",
    257: "RPL_ADMINLOC",
    258: "RPL_ADMINLOC",
    259: "RPL_ADMINEMAIL",
    263: "RPL_TRYAGAIN",
    401: "ERR_NOSUCHNICK",
    402: "ERR_NOSUCHSERVER",
    403: "ERR_NOSUCHCHANNEL",
    404: "ERR_CANNOTSENDTOCHAN",
    405: "ERR_TOOMANYCHANNELS",
    406: "ERR_WASNOSUCHNICK",
    407: "ERR_TOOMANYTARGETS",
    408: "ERR_NOSUCHSERVICE",
    409: "ERR_NOORIGIN",
    411: "ERR_NORECIPIENT",
    412: "ERR_NOTEXTTOSEND",
    413: "ERR_NOTOPLEVEL",
    414: "ERR_WILDTOPLEVEL",
    415: "ERR_BADMASK",
    421: "ERR_UNKNOWNCOMMAND",
    422: "ERR_NOMOTD",
    423: "ERR_NOADMININFO",
    424: "ERR_FILEERROR",
    431: "ERR_NONICKNAMEGIVEN",
    432: "ERR_ERRONEUSNICKNAME",
    433: "ERR_NICKNAMEINUSE",
    436: "ERR_NICKCOLLISION",
    437: "ERR_UNAVAILRESOURCE",
    441: "ERR_USERNOTINCHANNEL",
    442: "ERR_NOTONCHANNEL",
    443: "ERR_USERONCHANNEL",
    444: "ERR_NOLOGIN",
    445: "ERR_SUMMONDISABLED",
    446: "ERR_USERSDISABLED",
    451: "ERR_NOTREGISTERED",
    461: "ERR_NEEDMOREPARAMS",
    462: "ERR_ALREADYREGISTRED",
    463: "ERR_NOPERMFORHOST",
    464: "ERR_PASSWDMISMATCH",
    465: "ERR_YOUREBANNEDCREEP",
    466: "ERR_YOUWILLBEBANNED",
    467: "ERR_KEYSET",
    471: "ERR_CHANNELISFULL",
    472: "ERR_UNKNOWNMODE",
    473: "ERR_INVITEONLYCHAN",
    474: "ERR_BANNEDFROMCHAN",
    475: "ERR_BADCHANNELKEY",
    476: "ERR_BADCHANMASK",
    477: "ERR_NOCHANMODES",
    478: "ERR_BANLISTFULL",
    481: "ERR_NOPRIVILEGES",
    482: "ERR_CHANOPRIVSNEEDED",
    483: "ERR_CANTKILLSERVER",
    484: "ERR_RESTRICTED",
    485: "ERR_UNIQOPPRIVSNEEDED",
    491: "ERR_NOOPERHOST",
    501: "ERR_UMODEUNKNOWNFLAG",
    502: "ERR_USERSDONTMATCH",
}
