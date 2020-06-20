#! /usr/bin/env python3

import json
import os
import sys
import threading
import time
import urllib.error as ue
import urllib.request as ur
import urllib.parse as up

__version__ = '0.1'
__doc__ = '''StaphMB - A Telegram Group Management Bot infected by _S. aureus_

Version:\n\t'''+str(__version__)

class APIError(Exception):
    def __init__(self,module,info):
        self.info = info
    def __str__(self):
        return 'Telegram Bot '+self.module+' Exception: '+self.info
    def __repr__(self):
        return '<TGBot Exception="'+self.module+'" Info="'+self.info+'" />'

class stdOut():
    def __init__(self,fName=None):
        self.fh = None if fName is None else open(fName,'a',1)
    def writeln(self,data):
        if self.fh is None:
            print('['+str(int(time.time()))+'] '+str(data))
        else:
            self.fh.write('['+str(int(time.time()))+'] '+str(data)+'\n')

class tgapi:
    __doc__ = 'tgapi - Telegram Chat Bot HTTPS API Wrapper'

    escape = lambda x:x.replace('&','&amp;').replace('<','&gt;').replace('>','&lt;')

    def __init__(self,apikey,logger=None,maxRetry=5):
        self.logOut = stdOut() if logger is None else logger
        self.target = 'https://api.telegram.org/bot'+apikey+'/'
        self.retry = maxRetry
        self.info = self.query('getMe')
        self.fork = []
        if self.info is None:
            raise APIError('API', 'Initialization Self-test Failed')
        self.logOut.writeln("Bot "+self.info["username"]+" connected to the Telegram API.")

    def query(self,met,parameter=None,retry=None):
        req = ur.Request(self.target+met,method='POST')
        req.add_header('User-Agent','StaphMbot/0.1 (+https://github.com/StephDC/StaphMbot)')
        if parameter is not None:
            req.add_header('Content-Type','application/json')
            req.data = json.dumps(parameter).encode('UTF-8')
        retryCount = 0
        maxRetry = retry if retry is not None else self.retry
        failed = True
        while failed:
            try:
                resp = ur.urlopen(req)
            except ue.HTTPError:
                if retryCount >= maxRetry:
                    raise APIError('API','Query HTTP Error')
            except ue.URLError:
                if retryCount >= maxRetry:
                    raise APIError('API','Query DNS Error')
            else:
                failed = False
                break
            self.logOut.writeln("Query failed. Try again in 5 sec.")
            self.logOut.writeln("Failed Request:\nMethod: "+met+"\nParameters: "+str(parameter))
            time.sleep(5)
            retryCount += 1
        data = json.loads(resp.read().decode('UTF-8'))
        return data['result'] if data['ok'] else None

    def dQuery(self,delay,met,parameter=None,retry=None):
        time.sleep(delay)
        return self.query(met,parameter,retry)

    def delayQuery(self,delay,met,parameter=None,retry=None):
        t = threading.Thread(target=dQuery,args=(delay,met,parameter,retry))
        t.start()
        self.fork.append(t)

    def clearFork(self):
        'clearFork - join all forks that has completed'
        result = 0
        for item in self.fork:
            if item.is_alive():
                result += 1
            else:
                item.join()
                self.fork.remove(item)
        return result
    
    def sendMessage(self,target,text,misc={}):
        misc['text'] = text
        misc['chat_id'] = target
        misc['parse_mode'] = misc['parse_mode'] if 'parse_mode' in misc else 'HTML'
        try:
            data = self.query('sendMessage',misc,retry=0)
        except APIError:
            if 'reply_to_message_id' in misc:
                misc.pop('reply_to_message_id')
            data = self.query('sendMessage',misc,retry=0)
        if data and data['text'] == text:
            return data['message_id']
        else:
            return False

def randomID():
    return hex(int.from_bytes(os.urandom(8),'big'))[2:]

def getName(uid,gid,api,lookup={}):
    if uid in lookup:
        return '@'+lookup[uid]
    try:
        result = api.query('getChatMember',{'chat_id':int(gid),'user_id':int(uid)},retry=1)
    except APIError:
        return 'a former member of this group'
    return getNameRep(result['user'])

def getNameRep(userObj):
    '''Takes a TG User object and returns a HTML encoded User with link'''
    name = ''
    if 'username' in userObj:
        name = userObj['username']
    elif 'last_name' in userObj:
        name = userObj['first_name']+' '+userObj['last_name']
    else:
        name = userObj['first_name']
    if 'id' in userObj:
        return '<a href="tg://user?id='+str(userObj['id'])+'">'+tgapi.escape(name)+'</a>'
    else:
        return '@'+tgapi.escape(name)

def getMsgFile(msgObj):
    fileType = "MultimediaMessage"
    if 'photo' in msgObj:
        fileID = msgObj['photo'][-1]['file_id']
        fileType = "Photo"
    elif 'sticker' in msgObj:
        fileID = msgObj['sticker']['file_id']
        fileType = "Sticker"
        if 'emoji' in msgObj['sticker']:
            fileType += ' emoji="'+msgObj['sticker']['emoji']+'"'
    elif 'animation' in msgObj:
        fileID = msgObj['animation']['file_id']
        fileType = "Animation"
    elif 'voice' in msgObj:
        fileID = msgObj['voice']['file_id']
        fileType = 'Voice'
    ## Customize code for File URL
    result = '<'+fileType+' file_id="'+str(fileID)+'">'
    ## Customize end
    if 'caption' in msgObj:
        result  += ' '+msgObj['caption']
    return result

def getMsgText(msgObj):
    if 'text' not in msgObj:# and 'sticker' not in msgObj:
        print(repr(msgObj))
    return msgObj['text'] if 'text' in msgObj \
            else getMsgFile(msgObj) if (('sticker' in msgObj) or ('photo' in msgObj) or ('animation' in msgObj) or ('voice') in msgObj) \
            else ('<Dice value="'+str(msgObj['dice']['value'])+'">') if 'dice' in msgObj \
            else ('<MultimediaMessage> '+msgObj['caption']) if 'caption' in msgObj \
            else '<MultimediaMessage>'

def getMsg(msgObj):
    return(('tg',msgObj['chat']['id']),{'name':getNameRep(msgObj['from'])[1:],'text':getMsgText(msgObj)})
