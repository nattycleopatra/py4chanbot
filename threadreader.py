#! /usr/bin/env python3
#
# 4chan thread live shitposter IRC bot

from __future__ import unicode_literals, absolute_import, print_function, division

import time
import re
from io import StringIO

import threading
from threading import Thread

import basc_py4chan
from basc_py4chan.util import clean_comment_body
import irc.client

import sys

# configuration here
irc_server = 'irc.rizon.net'
irc_port = 6670
irc_nick = 'emugentxt'
#irc_nick = 'hbgtxt'
#irc_channel = '#emugentest'
irc_channel = '/#emugen/'
board_name = 'vg'
general = 'emugen|emulation' # matching pattern to find thread
#general = 'hbg|homebrew' # matching pattern to find thread


board = basc_py4chan.Board(board_name)
threadid = 0
thread = board.get_thread(threadid)

archive = 'boards.fireden.net'
archive_url = 'https://' + archive + '/' + board_name + '/thread/' + str(thread.topic.post_id)

def print_new_posts():
    update = thread.update()
    if (update > 0):
        new_posts = thread.posts[-update:]
        for post in new_posts:
            output = StringIO(newline='')
            #print("New post", post.post_id, "::")
            print('[{}] '.format(post.post_id),end="",file=output)
            if post.name != 'Anonymous':
                print('[name: '.end="",file=output)
                if post.name != 'None':
                    print('{}'.format(post.name),end="",file=output)
                if not post.tripcode is None:
                    print(post.tripcode,end="",file=output)
                print('] ',end="",file=output)
            if post.has_file:
                print('[img: {}]'.format(post.file_url),file=output)
            comment = post.text_comment
            lines = comment.split('\n')
            for line in lines:
                if not re.match(r'^\s*$', line):
                    print(line,file=output)
            print(output.getvalue(),end="")
            output.close()

def set_thread(board, threadid):
    global thread
    thread = board.get_thread(threadid)

def thread_alive(board, threadid):
    if (board.thread_exists(threadid)):
        return True
    else:
        return False

def find_current_thread(board, general):
    for thread in board.get_all_threads():
        if re.search(general, thread.topic.subject, re.I):
            print('Found current thread:', thread.url)
            return thread.topic.post_id
    print("No thread up at the moment")
    return -1

def chat_all_new_posts(c, target):
    update = thread.update()
    if (thread_alive(board, threadid)):
        if (update > 0):
            new_posts = thread.posts[-update:]
            for post in new_posts:
                output = StringIO(newline='')
                #print("New post", post.post_id, "::")
                print('[\x02\x0310{}\x0f] '.format(post.post_id),end="",file=output)
                if post.name != 'Anonymous':
                    print('[name: {}'.format(post.name),end="",file=output)
                    if not post.tripcode is None:
                        print(post.tripcode,end="",file=output)
                    print('] ',end="",file=output)
                if post.has_file:
                    print('[img: {}]'.format(https_url(post.file_url)),file=output)
                comment = post.comment
                if re.search('<s>', comment):
                    comment = comment.replace('<s>', '\x0301,01')
                    comment = comment.replace('</s>', '\x0f')
                    comment = clean_comment_body(comment)
                else:
                    comment = post.text_comment
                lines = comment.split('\n')
                for line in lines:
                    if not re.match(r'^\s*$', line):
                        quote = r'>>((\d+)|(((>(/\w+)*)*)))'
                        if re.search(quote, line):
                            splitline = line.split(' ')
                            for i, word in enumerate(splitline):
                                if re.match(quote, word):
                                    word = '\x0304', word, '\x0f'
                                    splitline[i] = ('').join(word)
                            line = (' ').join(splitline)
                        greentext = '^>[^>\n]+$'
                        if re.match(greentext, line):
                            print('\x0303{}\x0f'.format(line),file=output)
                        else:
                            print(line,file=output)

                for line in output.getvalue().split('\n'):
                    c.privmsg(target, line)
                print(output.getvalue(),end="")

                output.close()
            return True
        else:
            print('No new posts')
            return False
    else:
        print('Thread is dead')
        c.privmsg(target, "Thread 404'd: " + archive_url)
        set_thread(board, wait_for_new_thread())
        discovered = 'Found new thread: ' + https_url(thread.url)
        c.privmsg(target, discovered)
        return True

def wait_for_new_thread():
    new_id = find_current_thread(board, general)
    
    check_interval = 10
    while (new_id < 1):
        time.sleep(check_interval)
        new_id = find_current_thread(board, general)
        if check_interval < 120:
            check_interval += 5

    return new_id

def feed_loop(c, target):
    print('Bot started up')
    check_interval = 0
    while (1):
        time.sleep(check_interval)
        if (chat_all_new_posts(c, target)):
            check_interval = 5
        else:
            if (check_interval < 30):
                check_interval += 5
            print("Waiting {} seconds".format(check_interval))

def https_url(url):
    return url.replace('http', 'https')

def main():
    global target
    global threadid

    id = threadid

    if thread_alive(board, id):
        print("Thread be up.")
    else:
        while (id < 2):
            id = find_current_thread(board, general)
            if (id == -1):
                time.sleep(60)
        set_thread(board, id)
        threadid = id
    print(thread)

    reactor = irc.client.Reactor()
    try:
        c = reactor.server()
        c.connect(irc_server, irc_port, irc_nick)

        c.join(irc_channel)
        c.set_keepalive(60)

        t = threading.Thread(target=feed_loop, args=(c,irc_channel,))
        t.start()

        print('Bot runloop started')

    except irc.client.ServerConnectionError:
        print(sys.exc_info()[1])
        raise SystemExit(1)


    print('Finished trying')
    reactor.process_forever()


if __name__ == '__main__':
    main()
