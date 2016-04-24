#! /usr/bin/env python3
#
# 4chan thread live shitposter IRC bot

from __future__ import unicode_literals, absolute_import, print_function, division

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


cfg = configparser.ConfigParser()
cfg.read('config.cfg')

# configuration here
irc_server = cfg['IRC'].get('server', fallback='irc.rizon.net')
irc_port = cfg['IRC'].getint('port', fallback=6697)
irc_nick = cfg['IRC'].get('nick', fallback='pyemugenbot')
irc_channel = cfg['IRC'].get('channel', fallback='#emugentest')
irc_nickserv = cfg['IRC'].get('nickserv', fallback='NickServ')
irc_nickpass = cfg['IRC'].get('nickserv_password', fallback='')
admins = cfg['IRC'].get('admins', fallback='').split(',') # comma separated list of users who can restart and shutdown the bot

board_name = cfg['4chan'].get('board', fallback='vg')
general = cfg['4chan'].get('general', fallback='emugen|emulation') # matching pattern to find thread
archive = cfg['4chan'].get('archive', fallback='boards.fireden.net')
https = cfg['4chan'].getboolean('https', fallback=True)

DEBUG_PRINT = cfg['general'].getboolean('debug', fallback=True)

board = basc_py4chan.Board(board_name, https)
thread = board.get_thread(0)
bumplimit_warning = True


def archive_url():
    return 'https://' + archive + '/' + board_name + '/thread/' + str(thread.topic.post_id)

def set_thread(board, thread_id):
    global thread
    thread = board.get_thread(thread_id)

def thread_alive(board, thread):
    #return (board.thread_exists(thread_id))
    return board.thread_exists(thread.id) and thread.archived == False

def find_threads(board, general, search_comment=False):
    threads = set()
    for thread in board.get_all_threads():
        if thread.topic.subject is not None:
            if re.search(general, thread.topic.subject, re.I):
                threads.add(thread)
        if search_comment:
            if re.search(general, thread.topic.comment, re.I):
                threads.add(thread)
    return threads

def find_current_thread(board, general):
    for thread in board.get_all_threads():
        if thread.topic.subject is not None:
            if re.search(general, thread.topic.subject, re.I):
                print_debug('Found current thread: {}'.format(thread.url))
                return thread.topic.post_id
    print_debug('No thread up at the moment')
    return -1

def youtube_match(string):
    youtube = r'(youtu(?<=(v|V)/)|(?<=be/)|(?<=(\?|\&)v=)|(?<=embed/))([\w-]+)'
    return re.search(youtube, string)

def youtube_video_title_lookup(string, include_url=False):
    yt_match = youtube_match(string)
    if yt_match: #youtube handling
        splitline = string.split(' ')
        import urllib
        from bs4 import BeautifulSoup
        try:
            for i, word in enumerate(splitline):
                if youtube_match(word):
                    video_id = yt_match.group(0)
                    bs = BeautifulSoup(urllib.request.urlopen('https://www.youtube.com/watch?v=' + video_id), 'html.parser') # html.parser is 7% slower than lxml
                    video_title = bs.title.string[0:-10]
                    if not video_title:
                        return string
                    word= '[You\x0301,05Tube\x0f] \x0304' + video_title + '\x0f'
                    if include_url:
                        word = word + ' [https://youtu.be/' + video_id + ']'
                    splitline[i] = ('').join(word)
            string = (' ').join(splitline)
        except urllib.error.HTTPError as e:
            print_debug('Got HTTP error {} attempting to open YouTube link'.format(str(e.code)), 'ERROR')
    return string

def update_thread():
    update = -1
    tries = 0
    while tries < 10:
        try:
            update = thread.update()
            break
        except requests.exceptions.RequestException as e:
            print_debug('Update attempt led to request exception with code {}'.format(str(e.response.status_code)), 'ERROR')
            time.sleep(5+tries)
            continue
        tries += 1
    return update

def chat_new_posts(c, target):
    update = update_thread()
    if update == -1:
        return False
    if (thread_alive(board, thread)):
        if (update > 0):
            new_posts = thread.posts[-update:]
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
                    # File.filename_original attribute has been merged upstream but is not yet in release
                    # https://github.com/bibanon/BASC-py4chan/commit/205d001
                    print('[\x0314file:\x0f {} (\x0319{}\x0f)]'.format(post.file_url, post.file.filename_original),end='',file=output)
                print(file=output)
                comment = post.comment
                if re.search('<s>', comment):
                    comment = comment.replace('<s>', '\x0301,01')
                    comment = comment.replace('</s>', '\x0f')
                comment = basc_py4chan.util.clean_comment_body(comment)
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

                print_debug(output.getvalue(), 'POST', False)
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
                                if not c.is_connected():
                                    c.reconnect()
                                c.privmsg(target, wrapped)
                            except:
                                print_debug(sys.exc_info()[0], 'ERROR')
                        buffer = ''

                output.close()
            return True
        else:
            print_debug('No new posts')
            global bumplimit_warning
            if thread.bumplimit:
                print_debug('Bump limit reached ({} posts), looking for new thread'.format(len(thread.posts)), 'WARNING')
                old_thread = thread.id
                set_thread(board, wait_for_new_thread())
                if thread.id != old_thread:
                    discovered = '[\x0308ATTENTION!\x0f] Discovered next thread: ' + thread.url
                    print_debug(discovered)
                    c.privmsg(target, discovered)
                    bumplimit_warning = True
                    return True
                else:
                    if bumplimit_warning:
                        warning = '[\x0305WARNING!\x0f] Current thread has now reached the \x0307bump limit\x0f!'
                        c.privmsg(target, warning)
                        bumplimit_warning = False
            return False
    else:
        print_debug('Thread is dead ' + str(thread.topic.post_id), 'WARNING')
        c.privmsg(target, '[\x0305WARNING!\x0f] THREAD IS \x0305DEAD\x0f! Archive URL: ' + archive_url())
        set_thread(board, wait_for_new_thread())
        discovered = '[\x0308ATTENTION!\x0f] Discovered new thread: ' + thread.url
        print_debug(discovered)
        c.privmsg(target, discovered)
        return True

def wait_for_new_thread():
    new_id = find_current_thread(board, general)
    
    check_interval = 10
    while (new_id < 1):
        print_debug('Waiting for thread - {}s refresh'.format(check_interval))
        time.sleep(check_interval)
        new_id = find_current_thread(board, general)
        if check_interval < 120:
            check_interval += 5

    return new_id

def feed_loop(c, target):
    print_debug('Bot started up, looking for thread')
    set_thread(board, wait_for_new_thread())
    check_interval = 5
    while (1):
        time.sleep(check_interval)
        if (chat_new_posts(c, target)):
            check_interval = 5
        else:
            if (check_interval < 30):
                check_interval += 5
            print_debug('Waiting {} seconds'.format(check_interval))

def on_pubmsg(connection, event):
    args = event.arguments[0]
    yt_match = youtube_match(args)
    if re.search('^' + connection.get_nickname() + ':', args):
        print_debug('Detected my own nick mentioned')
        split_args = args.split(' ')
        cmd = split_args[1]
        if (cmd == 'thread'):
            connection.privmsg(irc_channel, thread.url)
        elif (cmd == 'posts'):
            connection.privmsg(irc_channel, 'Thread is currently at ' + str(len(thread.posts)) + ' posts')
        elif (cmd == 'ppm' or cmd == 'speed'):
            time_since = int(time.time()) - thread.topic.timestamp
            ppm = len(thread.posts) / (time_since / 60)
            connection.privmsg(irc_channel, '{0:.2f} posts per minute'.format(ppm))
        elif (cmd == 'search'):
            if len(args.split(' ')) > 3:
                invalid_board = True
                for board in basc_py4chan.get_all_boards():
                    if split_args[2] == board.name:
                        invalid_board = False
                        print_debug('Board found')
                        search_board = basc_py4chan.Board(split_args[2], https)
                        threads = find_threads(search_board, (' ').join(split_args[3:]), True)
                        if len(threads) > 0:
                            print_debug('Thread(s) found')
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
                                connection.privmsg(irc_channel, message)
                        else:
                            connection.privmsg(irc_channel, 'No such thread')
                if invalid_board:
                    connection.privmsg(irc_channel, 'No such board')
            else:
                connection.privmsg(irc_channel, 'Not enough arguments')
        elif (cmd == 'commands'):
            commands = ['thread: returns URL to current thread',
                        'posts: returns post count of current thread',
                        'ppm|speed: returns the average posts per minute for this thread'
                        'search <board> <thread>: returns thread title and URL if found'
                       ]
            for msg in commands:
                connection.privmsg(event.source.nick, msg)
        else:
            if (event.source.nick in admins):
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
            connection.privmsg(irc_channel, msg)

def on_privmsg(connection, event):
    args = event.arguments[0]
    split_args = args.split(' ')
    cmd = split_args[0]
    print_debug(args)
    if (event.source.nick in admins):
        if (cmd == 'msg'):
            msg = (' ').join(split_args[2:])
            connection.privmsg(split_args[1], msg)
        if (cmd == 'restart'):
            connection.disconnect('Restarting...')
            import os
            os.execv(__file__, sys.argv)
    if (event.source.nick not in admins):
        for admin in admins:
            connection.privmsg(admin, '<{}> '.format(event.source.nick) + args)

def on_ctcp(connection, event):
    if event.arguments[0] == 'VERSION':
        connection.ctcp_reply(event.source.nick, 'VERSION pyemugenbot 0.1')

def on_disconnect(connection, event):
    time.sleep(3)
    connection.reconnect()

def on_welcome(connection, event):
    if irc_nickpass:
        connection.privmsg(irc_nickserv, 'IDENTIFY ' + irc_nickpass)
    connection.join(irc_channel)

def print_debug(msg, type='INFO', newline=True, time_display=True):
    if DEBUG_PRINT:
        message = '[{}] {}'.format(type, msg)
        if time_display:
            message = '[' + time.strftime('%Y-%m-%d %H:%M:%S') + '] ' + message
        if newline:
            print(message)
        else:
            print(message, end='')

def main():
    reactor = irc.client.Reactor()
    try:
        c = reactor.server()
        c.buffer_class = irc.buffer.LenientDecodingLineBuffer
        c.connect(irc_server, irc_port, irc_nick)

        c.set_keepalive(60)

        c.add_global_handler('pubmsg', on_pubmsg)
        c.add_global_handler('privmsg', on_privmsg)
        #c.add_global_handler('privnotice', on_privmsg)
        c.add_global_handler('ctcp', on_ctcp)
        c.add_global_handler('welcome', on_welcome)
        c.add_global_handler('disconnect', on_disconnect)

        t = threading.Thread(target=feed_loop, args=(c,irc_channel,))
        t.start()

        print_debug('Bot runloop started')

    except irc.client.ServerConnectionError:
        print(sys.exc_info()[0])
        raise SystemExit(1)


    print_debug('Main process moving into connection maintainance')
    while True:
        reactor.process_forever()
    except timeout:
        print_debug('Error: timeout from socket connection')
        continue


if __name__ == '__main__':
    main()
