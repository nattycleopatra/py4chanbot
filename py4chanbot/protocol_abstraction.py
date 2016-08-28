#! /usr/bin/env python3

import configparser
from .helper import debugprint
import logging

class ProtocolAbstraction(object):
    irc = None
    discord = None

    def __init__(self, config):
        logging.basicConfig(level=logging.DEBUG,
                datefmt='%m-%d %H:%M')
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(console)

        irc = config['IRC'].getboolean('enable', fallback=False)
        discord = config['Discord'].getboolean('enable', fallback=False)

        if irc:
            self.irc_init(config)

        if discord:
            self.discord_init(config)

    def irc_init(self, config):
        debugprint('irc init start')
        server = config['IRC'].get('server', fallback='irc.rizon.net')
        port = config['IRC'].getint('port', fallback=6697)
        nick = config['IRC'].get('nick', fallback='pyemugenbot')
        channels = config['IRC'].get('channels', fallback='#emugentest').split(',')
        nickserv = config['IRC'].get('nickserv', fallback='NickServ')
        nickpass = config['IRC'].get('nickserv_password', fallback='')
        admins = config['IRC'].get('admins', fallback='').split(',') # comma separated list of users who can restart and shutdown the bot 

        from .protocols import irc

        self.irc = irc.IRC(server=server, port=port, nick=nick, channels=channels, nickserv=nickserv, nickpass=nickpass, admins=admins)

        debugprint('irc init done')
        return 0

    def discord_init(self, config):
        debugprint('discord init start')

        token = config['Discord'].get('token', fallback='')
        channels = config['Discord'].get('channels', fallback='').split(',')

        from .protocols import discord

        self.discord = discord.Discord(token=token, channels=channels)

        debugprint('discord init done')

    def chat(self, msg='', post={}, channels='', type=''):
        if self.irc is not None:
            self.irc.chat(msg=msg, post=post, type='')
        if self.discord is not None:
            self.discord.chat(msg=msg, post=post, type='')
