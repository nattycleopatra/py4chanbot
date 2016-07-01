#! /usr/bin/env python3

import re
import time
from html.parser import HTMLParser

# adapted from basc_py4chan's HTML cleanup function
def clean_comment_body(body):
    """Returns given comment HTML as plaintext.

    Converts all HTML tags and entities within 4chan comments
    into human-readable text equivalents.
    """
    parser = HTMLParser()
    body = parser.unescape(body)
    body = re.sub(r'<a [^>]+>(.+?)</a>', r'\1', body)
    body = body.replace('<br>', '\n')
    body = re.sub(r'</?(span|a|p|quoteblock|quote|code).*?>', '', body)
    return body

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
            debugprint('Got HTTP error {} attempting to open YouTube link'.format(str(e.code)), 'ERROR')
    return string

def debugprint(msg, type='INFO', newline=True, time_display=True):
    message = '[{}] {}'.format(type, msg)
    if time_display:
        message = '[' + time.strftime('%Y-%m-%d %H:%M:%S') + '] ' + message
    if newline:
        print(message)
    else:
        print(message, end='')
