#!/usr/bin/env python3

import os, stat
import threading
import sqlite3 as sql
import re

import telegram
import discord

class ThreadedSQLite(object):
    def __init__(self, dburi):
        self.lock = threading.Lock()
        self.connection = sql.connect(dburi, check_same_thread=False)
        self.connection.row_factory = sql.Row
        self.cursor = None
    def __enter__(self):
        self.lock.acquire()
        self.cursor = self.connection.cursor()
        return self
    def __exit__(self, type, value, traceback):
        self.lock.release()
        self.connection.commit()
        if self.cursor is not None:
            self.cursor.close()
            self.cursor = None

class RepeatingTimer(object):

    def __init__(self, interval, f, *args, **kwargs):
        self.interval = interval
        self.f = f
        self.args = args
        self.kwargs = kwargs

        self.timer = None

    def callback(self):
        self.f(*self.args, **self.kwargs)
        self.start()

    def cancel(self):
        if self.timer != None:
            self.timer.cancel()

    def start(self):
        self.timer = threading.Timer(self.interval, self.callback)
        self.timer.start()

def validateName( name ):
   return re.match('^[a-zA-Z0-9.,#-]{1,20}$',name)

def validateIp( name ):
 return re.match('^(?:(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])(\.(?!$)|$)){4}$',name)

def isInt(s):
    try:
        int(s)
        return True
    except:
        return False

def pathIsWritable(path):
    mode = os.lstat(path)[stat.ST_MODE]
    return True if mode & stat.S_IWUSR else False

def secondsToText(secs):
    days = secs//86400
    hours = (secs - days*86400)//3600
    minutes = (secs - days*86400 - hours*3600)//60
    seconds = secs - days*86400 - hours*3600 - minutes*60
    result = ("{0} day{1}, ".format(days, "s" if days!=1 else "") if days else "") + \
    ("{0} hour{1}, ".format(hours, "s" if hours!=1 else "") if hours else "") + \
    ("{0} minute{1}, ".format(minutes, "s" if minutes!=1 else "") if minutes else "") + \
    ("{0} second{1} ".format(seconds, "s" if seconds!=1 else "") if seconds else "")
    return result if result != "" else "Now"

def crossMessengerSplit(obj):

    result = {'user': None, 'name': None, 'chat':None}

    if isinstance(obj, telegram.update.Update):
        #Telegram
        result['user'] = obj.message.from_user.id
        result['name'] = obj.message.from_user.name
        result['chat'] = obj.message.chat_id
    elif isinstance(obj.author, discord.Member) or \
         isinstance(obj.author, discord.User):
        #Discord public/private message
        result['user'] = obj.author.id
        result['name'] = obj.author.name
        result['chat'] = obj.channel.id

    return result

def memcmp ( str1, str2, count):

    while count > 0:
        count -= 1
        
        if str1[count] != str2[count]:
            return -1 if str1[count] < str2[count] else 1

    return 0
