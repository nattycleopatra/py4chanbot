#! /usr/bin/env python3

from py4chanbot import ThreadBot
from configparser import ConfigParser

config = ConfigParser()
config.read('config.cfg')
ThreadBot(config).main()
