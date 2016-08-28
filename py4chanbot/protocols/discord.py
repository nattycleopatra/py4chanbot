#! /usr/bin/env python3

import discord
import asyncio
import threading
import re

from .. import __version__
from ..helper import clean_comment_body, debugprint

class Discord(discord.Client):
    channels = []

    def __init__(self, token='', channels=''):
        super(Discord, self).__init__()

        loop = asyncio.get_event_loop()

        self._channels_text = channels

        t = threading.Thread(target=self.exec,args=(loop,token,))
        t.start()

    def exec(self, loop, token):
        asyncio.set_event_loop(loop)
        self.run(token)

    @asyncio.coroutine
    def on_ready(self):
        ch_txt = self._channels_text
        for ch in self.get_all_channels():
            for txt in self._channels_text:
                if txt[0] == '#':
                    txt = txt[1:]
                if ch.name == txt:
                    self.channels.append(ch)

    def chat(self, msg='', post={}, channels='', type=''):
        if post:
            msg = self.format_post(post)
        elif type:
            warning = ':warning:'
            if type == 'discovered':
                thread_url = msg
                hand = ':ok_hand:'
                msg = self.bold(hand*3 + ' ATTENTION: ' + hand*3)
                msg += 'New thread discovered!\n' + self.bold('URL: ') + thread_url + '\n' + msg
            elif type == 'bumplimit':
                msg = self.bold(warning*3 + ' WARNING ' + warning*3)
                msg += '\nBump limit has been reached\n' + msg
            elif type == 'dead':
                archive = msg
                msg = self.bold(warning*6 + ' WARNING ' + warning*6)
                msg += '\nThe thread is ' + self.bold('DEAD') + '\nArchive: ' + archive + msg
        if msg:
            for channel in self.channels:
                if channel.type.value is not 2:
                    asyncio.run_coroutine_threadsafe(self.send_message(channel, msg), self.loop).result()

    def format_post(self, post={}):
        s = '[' + self.bold(str(post.get('id'))) + '] '
        if 'name'in post:
            s += '[' + self.bold('name: ') + post.get('name')
            if 'tripcode' in post:
                s += self.italic(post.get('tripcode'))
            s += '] '
        if 'fileurl' in post:
            s += '[' + self.bold('file: ') + post.get('fileurl') + ' (' + post.get('filename') + ')] '
        if s:
            s += '\n'

        if 'comment' in post:
            comment = clean_comment_body(self.spoiler(post.get('comment')))
            lines = comment.split('\n')
            quote = r'>>((\d+)|>((((/\w+)*)*)/?))'
            for line in lines:
                if not re.match(r'^\s*$', line): # no checking of blank lines
                    if re.search(quote, line):
                        splitline = line.split(' ')
                        for i, word in enumerate(splitline):
                            if re.match(quote, word): # quote handling
                                word = self.underline(word)
                                splitline[i] = ('').join(word)
                        line = (' ').join(splitline)

                greentext = '^>[^>\n]+$'
                if re.match(greentext, line):
                    s += self.italic(line) + '\n'
                else:
                    s += line + '\n'
        return s

    def contains_spoiler(self, s=''):
        if re.search('<s>', s):
            return True
        return False

    def spoiler(self, s=''):
        if self.contains_spoiler(s):
            s = s.replace('<s>', '~~')
            s = s.replace('</s>', '~~')
        return s

    def bold(self, s=''):
        return '**' + s + '**'

    def italic(self, s=''):
        return '*' + s + '*'

    def underline(self, s=''):
        return '__' + s + '__'
