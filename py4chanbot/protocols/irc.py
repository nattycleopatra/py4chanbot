#! /usr/bin/env python3

import re
import time
import threading
import irc.client
import basc_py4chan
from socket import timeout

from .. import __version__
from ..helper import youtube_match, youtube_video_title_lookup, debugprint

class IRC(object):

    def __init__(self, server='', port='', nick='', channels='', nickserv='', nickpass='', admins=''):
        self._reactor = irc.client.Reactor()
        try:
            connection = self._reactor.server()
            connection.buffer_class = irc.buffer.LenientDecodingLineBuffer

            connection.set_keepalive(60)

            connection.add_global_handler('pubmsg', self.on_pubmsg)
            connection.add_global_handler('privmsg', self.on_privmsg)
            connection.add_global_handler('ctcp', self.on_ctcp)
            connection.add_global_handler('welcome', self.on_welcome)
            connection.add_global_handler('disconnect', self.on_disconnect)

            self._channels = channels
            self._nickserv = nickserv
            self._nickpass = nickpass
            self._admins = admins
            connection.connect(server, port, nick)

            self._irc_channel = self._channels # temporary hack

            self._connection = connection

        except irc.client.ServerConnectionError:
            print(sys.exc_info()[0])
            raise SystemExit(1)

        thread = threading.Thread(target=self.start, args=())
        thread.daemon = True
        thread.start()

    def get_connection(self):
        return self._connection

    def chat(self, msg=''):
        for channel in self._channels:
            self._connection.privmsg(channel, msg)

    def connection_maintenance(self):
        while True:
            try:
                self._reactor.process_forever()
            except timeout:
                debugprint('Error: timeout from socket connection')
                continue


    def on_pubmsg(self, connection, event):
        args = event.arguments[0]
        yt_match = youtube_match(args)
        if re.search('^' + connection.get_nickname() + ':', args):
            debugprint('Detected my own nick mentioned')
            split_args = args.split(' ')
            cmd = split_args[1]
            if (cmd == 'thread'):
                connection.privmsg(self._irc_channel, self._thread.url)
            elif (cmd == 'posts'):
                connection.privmsg(self._irc_channel, 'Thread is currently at ' + str(len(self._thread.posts)) + ' posts')
            elif (cmd == 'ppm' or cmd == 'speed'):
                time_since = int(time.time()) - self._thread.topic.timestamp
                ppm = len(self._thread.posts) / (time_since / 60)
                connection.privmsg(self._irc_channel, '{0:.2f} posts per minute'.format(ppm))
            elif (cmd == 'search'):
                if len(args.split(' ')) > 3:
                    invalid_board = True
                    for board in basc_py4chan.get_all_boards():
                        if split_args[2] == board.name:
                            invalid_board = False
                            debugprint('Board found')
                            search_board = basc_py4chan.Board(split_args[2], self._https)
                            threads = self.find_threads(search_board, (' ').join(split_args[3:]), True)
                            if len(threads) > 0:
                                debugprint('Thread(s) found')
                                for found_thread in threads:
                                    subject = found_thread.topic.subject
                                    comment = found_thread.topic.text_comment
                                    if subject is not None:
                                        message = '\x0304' + found_thread.topic.subject + '\x0f'
                                    else:
                                        line = comment.split('\n')[0]
                                        maxlength = 50
                                        if len(line) > maxlength:
                                            message = '\x0304' + line[:maxlength] + '...' + '\x0f'
                                        else:
                                            message = '\x0304' + line + '\x0f'
                                    message = message + ': ' + found_thread.url
                                    connection.privmsg(self._irc_channel, message)
                            else:
                                connection.privmsg(self._irc_channel, 'No such thread')
                    if invalid_board:
                        connection.privmsg(self._irc_channel, 'No such board')
                else:
                    connection.privmsg(self._irc_channel, 'Not enough arguments')
            elif (cmd == 'commands'):
                commands = ['thread: returns URL to current thread',
                            'posts: returns post count of current thread',
                            'ppm|speed: returns the average posts per minute for this thread'
                            'search <board> <thread>: returns thread title and URL if found'
                           ]
                for msg in commands:
                    connection.privmsg(event.source.nick, msg)
            else:
                if (event.source.nick in self._admins):
                    if (cmd == 'restart'):
                        connection.disconnect('As you wish my lord...')
                        import os
                        os.execv(__file__, sys.argv)
                    elif (cmd == 'quit' or cmd == 'die'):
                        connection.disconnect('Yes master...')
                        sys.exit()
                    elif (cmd == 'msg'):
                        if len(args.split(' ')) > 3:
                            msg = (' ').join(split_args[3:])
                            connection.privmsg(split_args[2], msg)
        elif yt_match:
            output = []
            for part in args.split(' '):
                if youtube_match(part):
                    title = youtube_video_title_lookup(part)
                    if title != part:
                        output.append('↑↑ ' + title + ' ↑↑')
            for msg in output:
                connection.privmsg(self._irc_channel, msg)

    def on_privmsg(self, connection, event):
        args = event.arguments[0]
        split_args = args.split(' ')
        cmd = split_args[0]
        debugprint(args)
        if (event.source.nick in self._admins):
            if (cmd == 'msg'):
                msg = (' ').join(split_args[2:])
                connection.privmsg(split_args[1], msg)
            if (cmd == 'restart'):
                connection.disconnect('Restarting...')
                import os
                os.execv(__file__, sys.argv)
        if (event.source.nick not in self._admins):
            for admin in admins:
                connection.privmsg(admin, '<{}> '.format(event.source.nick) + args)

    def on_ctcp(self, connection, event):
        if event.arguments[0] == 'VERSION':
            connection.ctcp_reply(event.source.nick, 'VERSION py4chanbot ' + __version__)

    def on_disconnect(self, connection, event):
        time.sleep(3)
        connection.reconnect()

    def on_welcome(self, connection, event):
        if self._nickpass:
            connection.privmsg(self._irc_nickserv, 'IDENTIFY ' + self._irc_nickpass)
        for channel in self._channels:
            connection.join(channel)

    def start(self):
        self.connection_maintenance()
