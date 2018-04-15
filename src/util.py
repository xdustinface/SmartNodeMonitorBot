##
# Part of `SmartNodeMonitorBot`
#
# Copyright 2018 dustinface
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##

import os, stat
import threading
import sqlite3 as sql
import re

import telegram
import discord

def validateName( name ):

    if re.match('^[a-zA-Z0-9.,#-]{1,20}$',name):
        return name

    return None

def validateIp( ip ):

    if re.match('^(?:(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])(\.(?!$)|$)){3}(?:(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])(\.(?!$)|$|:9678)){1}$',ip):
        return ip.replace(':9678','')

    return None

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

    if days:
        seconds = -1
        minutes = -1

    result =  ("{0} day{1}, ".format(days, "s" if days!=1 else "") if days else "")
    result += ("{0} hour{1}{2} ".format(hours, "s" if hours!=1 else "", "," if minutes and not days else "") if hours else "")
    result += ("{0} minute{1}{2} ".format(minutes, "s" if minutes!=1 else "", "," if seconds and not minutes else "") if minutes and not days else "")
    result += ("{0} second{1} ".format(seconds, "s" if seconds!=1 else "") if seconds and not minutes else "")
    return result if result != "" else "Now"

def crossMessengerSplit(obj):

    result = {'user': None, 'name': None, 'chat':None, 'public':False}

    if isinstance(obj, telegram.update.Update):
        #Telegram
        result['user'] = obj.message.from_user.id
        result['name'] = obj.message.from_user.name
        result['chat'] = obj.message.chat_id
    elif isinstance(obj, discord.Member) or \
         isinstance(obj, discord.User):
        result['user'] = obj.id
        result['name'] = obj.name
    elif isinstance(obj.author, discord.Member) or \
         isinstance(obj.author, discord.User):
        #Discord public/private message
        result['user'] = obj.author.id
        result['name'] = obj.author.name
        result['chat'] = obj.channel.id
        result['public'] = isinstance(obj.author, discord.Member)

    return result

def memcmp ( str1, str2, count):

    while count > 0:
        count -= 1

        if str1[count] != str2[count]:
            return -1 if str1[count] < str2[count] else 1

    return 0
