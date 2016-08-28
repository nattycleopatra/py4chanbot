#! /usr/bin/env python3
#
# 4chan thread live shitposter IRC bot

import sys
import time
import re
import threading
import configparser
from socket import timeout

import requests
import basc_py4chan

from . import __version__
from .helper import clean_comment_body, youtube_match, youtube_video_title_lookup, debugprint
from .protocol_abstraction import ProtocolAbstraction

class ThreadBot(object):

    def __init__(self, config):
        self._connections = ProtocolAbstraction(config)

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
                    contents = {}
                    contents['id'] = post.post_id
                    if post.name != 'Anonymous':
                        if not post.name is None:
                            contents['name'] = post.name
                        if not post.tripcode is None:
                            contents['tripcode'] = post.tripcode
                    if post.has_file:
                        contents['fileurl'] = post.file_url
                        contents['filename'] = post.file.filename_original
                    contents['comment'] = post.comment

                    self._connections.chat(post=contents)
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
                        self._connections.chat(msg=self._thread.url, type='discovered')
                        self._bumplimit_warning = True
                        return True
                    else:
                        if self._bumplimit_warning:
                            debugprint('Current thread has reached the bump limit')
                            self._connections.chat(type='bumplimit')
                            self._bumplimit_warning = False
                return False
        else:
            self.print_debug('Thread is dead ' + str(self._thread.topic.post_id), 'WARNING')

            self._connections.chat(msg=self.archive_url(), type='dead')

            self.set_thread(self._board, self.wait_for_new_thread())
            discovered = '[\x0308ATTENTION!\x0f] Discovered new thread: ' + self._thread.url
            self.print_debug(discovered)

            self._connections.chat(msg='self._thread.url', type='discovered')
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
