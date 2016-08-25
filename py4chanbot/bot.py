#! /usr/bin/env python3
#
# 4chan thread live shitposter IRC bot

import sys
import time
import re
import threading
import configparser
from socket import timeout
from io import StringIO
import textwrap

import requests
import basc_py4chan
import irc.client

from . import __version__
from .helper import clean_comment_body, youtube_match, youtube_video_title_lookup, debugprint
from .protocol_abstraction import ProtocolAbstraction

class ThreadBot(object):

    def __init__(self, config):
        self._irc_enable = config['IRC'].get('enable', fallback=False)
        self._irc_server = config['IRC'].get('server', fallback='irc.rizon.net')
        self._irc_port = config['IRC'].getint('port', fallback=6697)
        self._irc_nick = config['IRC'].get('nick', fallback='pyemugenbot')
        self._irc_channel = config['IRC'].get('channel', fallback='#emugentest')
        self._irc_nickserv = config['IRC'].get('nickserv', fallback='NickServ')
        self._irc_nickpass = config['IRC'].get('nickserv_password', fallback='')
        self._admins = config['IRC'].get('admins', fallback='').split(',') # comma separated list of users who can restart and shutdown the bot

        self._connections = ProtocolAbstraction(config)
        self._irc_connection = self._connections.get_irc()

        self._connections.chat('this is a test')

        self._board_name = config['4chan'].get('board', fallback='vg')
        self._general = config['4chan'].get('general', fallback='emugen|emulation') # matching pattern to find thread
        self._archive = config['4chan'].get('archive', fallback='boards.fireden.net')
        self._https = config['4chan'].getboolean('https', fallback=True)

        self._DEBUG_PRINT = config['general'].getboolean('debug', fallback=True)

        self._board = basc_py4chan.Board(self._board_name, self._https)
        self._thread = self._board.get_thread(0)
        self._bumplimit_warning = True # Used for displaying bumplimit reached warning


    def archive_url(self):
        return 'https://' + self._archive + '/' + self._board_name + '/thread/' + str(self._thread.topic.post_id)

    def set_thread(self, board, thread_id):
        self._thread = board.get_thread(thread_id)

    def thread_alive(self, board, thread):
        return self._board.thread_exists(thread.id) and self._thread.archived == False

    def find_threads(self, board, general, search_comment=False):
        threads = set()
        for thread in board.get_all_threads():
            if thread.topic.subject is not None:
                if re.search(general, thread.topic.subject, re.I):
                    threads.add(thread)
            if search_comment:
                if re.search(general, thread.topic.comment, re.I):
                    threads.add(thread)
        return threads

    def find_current_thread(self, board, general):
        try:
            for thread in self._board.get_all_threads():
                if thread.topic.subject is not None:
                    if re.search(general, thread.topic.subject, re.I):
                        self.print_debug('Found current thread: {}'.format(thread.url))
                        return thread.topic.post_id
            self.print_debug('No thread up at the moment')
        except requests.exceptions.RequestException as e:
            self.print_debug('Board update attempt led to request exception with code {}'.format(str(e.response.status_code)), 'ERROR')
        return -1

    def update_thread(self):
        update = -1
        tries = 0
        while tries < 10:
            try:
                update = self._thread.update()
                break
            except requests.exceptions.RequestException as e:
                self.print_debug('Update attempt led to request exception with code {}'.format(str(e.response.status_code)), 'ERROR')
                time.sleep(5+tries)
                continue
            tries += 1
        return update

    def chat_new_posts(self):
        update = self.update_thread()
        if update == -1:
            return False
        if (self.thread_alive(self._board, self._thread)):
            if (update > 0):
                new_posts = self._thread.posts[-update:]
                for post in new_posts:
                    output = StringIO(newline='')
                    print('[\x02\x0310{}\x0f] '.format(post.post_id),end='',file=output)
                    if post.name != 'Anonymous':
                        print('[\x0314name:\x0f ',end='',file=output)
                        if not post.name is None:
                            print(post.name,end='',file=output)
                        if not post.tripcode is None:
                            print('\x0313{}\x0f'.format(post.tripcode),end='',file=output)
                        print('] ',end='',file=output)
                    if post.has_file:
                        print('[\x0314file:\x0f {} (\x0319{}\x0f)]'.format(post.file_url, post.file.filename_original),end='',file=output)
                    print(file=output)
                    comment = post.comment
                    if re.search('<s>', comment):
                        comment = comment.replace('<s>', '\x0301,01')
                        comment = comment.replace('</s>', '\x0f')
                    comment = clean_comment_body(comment)
                    lines = comment.split('\n')
                    quote = r'>>((\d+)|>((((/\w+)*)*)/?))'
                    for line in lines:
                        if not re.match(r'^\s*$', line): # no checking of blank lines
                            if re.search(quote, line):
                                splitline = line.split(' ')
                                for i, word in enumerate(splitline):
                                    if re.match(quote, word): # quote handling
                                        word = '\x0304', word, '\x0f'
                                        splitline[i] = ('').join(word)
                                line = (' ').join(splitline)

                            if youtube_match(line):
                                line = youtube_video_title_lookup(line, True)
                            greentext = '^>[^>\n]+$'
                            if re.match(greentext, line):
                                print('\x0303{}\x0f'.format(line),file=output)
                            else:
                                print(line,file=output)

                    self.print_debug(output.getvalue(), 'POST', False)
                    buffer = ''
                    for i, line in enumerate(output.getvalue().split('\n')):
                        if i == 0:
                            buffer = line
                            if buffer[-1] is not ' ':
                                buffer += ' '
                        elif re.match('\x0304' + quote + '\x0f', line):
                            buffer += line + ' '
                        else:
                            if buffer:
                                line = buffer + line
                            for wrapped in textwrap.wrap(line, 425): # IRC messages must be under 512 total bytes
                                try:
                                    #if not self._irc_connection.is_connected():
                                    #    self._irc_connection.reconnect()
                                    #self._irc_connection.privmsg(self._irc_channel, wrapped)
                                    self._connections.chat(msg=wrapped)
                                except:
                                    self.print_debug(sys.exc_info()[0], 'ERROR')
                            buffer = ''

                    output.close()
                return True
            else:
                self.print_debug('No new posts')
                if self._thread.bumplimit:
                    self.print_debug('Bump limit reached, looking for new thread', 'WARNING')
                    old_thread = self._thread.id
                    self.set_thread(self._board, self.wait_for_new_thread())
                    if self._thread.id != old_thread:
                        discovered = '[\x0308ATTENTION!\x0f] Discovered next thread: ' + self._thread.url
                        self.print_debug(discovered)
                        self._irc_connection.privmsg(self._irc_channel, discovered)
                        self._bumplimit_warning = True
                        return True
                    else:
                        if self._bumplimit_warning:
                            warning = '[\x0305WARNING!\x0f] Current thread has now reached the \x0307bump limit\x0f!'
                            self._irc_connection.privmsg(self._irc_channel, warning)
                            self._bumplimit_warning = False
                return False
        else:
            self.print_debug('Thread is dead ' + str(self._thread.topic.post_id), 'WARNING')
            self._irc_connection.privmsg(self._irc_channel, '[\x0305WARNING!\x0f] THREAD IS \x0305DEAD\x0f! Archive URL: ' + self.archive_url())
            self.set_thread(self._board, self.wait_for_new_thread())
            discovered = '[\x0308ATTENTION!\x0f] Discovered new thread: ' + self._thread.url
            self.print_debug(discovered)
            self._irc_connection.privmsg(self._irc_channel, discovered)
            return True

    def wait_for_new_thread(self):
        new_id = self.find_current_thread(self._board, self._general)

        check_interval = 10
        while (new_id < 1):
            self.print_debug('Waiting for thread - {}s refresh'.format(check_interval))
            time.sleep(check_interval)
            new_id = self.find_current_thread(self._board, self._general)
            if check_interval < 120:
                check_interval += 5

        return new_id

    def feed_loop(self):
        self.print_debug('Bot started up, looking for thread')
        self.set_thread(self._board, self.wait_for_new_thread())
        check_interval = 5
        while (1):
            time.sleep(check_interval)
            if (self.chat_new_posts()):
                check_interval = 5
            else:
                if (check_interval < 30):
                    check_interval += 5
                self.print_debug('Waiting {} seconds'.format(check_interval))

    def print_debug(self, msg, type='INFO', newline=True, time_display=True):
        if self._DEBUG_PRINT:
            debugprint(msg, type, newline, time_display)

    def main(self):
        thread = threading.Thread(target=self.feed_loop)
        thread.start()


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.cfg')
    ThreadBot(config).main()
