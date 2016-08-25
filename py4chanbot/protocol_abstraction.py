#! /usr/bin/env python3

import configparser
from .helper import debugprint
import logging

class ProtocolAbstraction(object):

    def __init__(self, config):
        logging.basicConfig(level=logging.DEBUG,
                datefmt='%m-%d %H:%M')
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        logging.getLogger('').addHandler(console)
        self._irc_enabled = config['IRC'].get('enable', fallback=False)

        if self._irc_enabled:
            self.irc_init(config)

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

        self._irc = irc.IRC(server=server, port=port, nick=nick, channels=channels, nickserv=nickserv, nickpass=nickpass, admins=admins)

        debugprint('irc init done')
        return 0

    def get_irc(self):
        if self._irc_enabled:
            return self._irc.get_connection

    def chat(self, msg='', channel=''):
        if self._irc_enabled:
            self._irc.chat(msg=msg)
