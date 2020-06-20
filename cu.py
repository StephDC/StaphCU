#! /usr/bin/env python3

import base64
import botconfig
import datetime
import os
import sqldb
import tg
import time

flaglist = ('op',) #List of available flags for admin

def csprng(checkdup=lambda x: True,maxtrial=5):
    '''Generate a random number in base64 that checkdup returns True'''
    for trial in range(maxtrial):
        r = base64.b64encode(os.urandom(15),b'-_')
        if checkdup(r):
            return r
    return False

def canPunish(api,gid):
    tmp = api.query('getChatMember',{'chat_id':gid,'user_id':api.info['id']})
    return tmp['status'] == 'creator' or ('can_restrict_members' in tmp and tmp['can_restrict_members'] and 'can_delete_messages' in tmp and tmp['can_delete_messages'])

def canSpeak(api,gid):
    try:
        tmp = api.query('getChatMember',{'chat_id':gid,'user_id':api.info['id']})
        return tmp['status'] in ('creator','administrator','member') or (tmp['status'] == 'restricted' and 'can_send_messages' in tmp and tmp['can_send_messages'])
    except tg.APIError:
        return False

def checkGroup(api,db,group,member,origMsg,ingroup=lambda a,b,c,d:True,outgroup=lambda a,b,c,d:True,finalMsg=None,af=0.5):
    '''checkGroup - Check if a user is in any of the groups specified in group
    If user is in a group, execute ingroup
    Else, execute outgroup
    API Format: {in,out}group(api,db,gid,uid)'''
    api.query('sendChatAction',{'chat_id':origMsg['chat']['id'],'action':'typing'})
    ct = time.time()
    for item in group:
        try:
            data = api.query('getChatMember',{'chat_id':item,'user_id':member},retry=0)
            if data['status'] in ('kicked','left','restricted'):
                outgroup(api,db,item,member)
            else:
                ingroup(api,db,item,member)
        except tg.APIError:
            outgroup(api,db,item,member)
        time.sleep(af)
        if time.time()-ct > 4.2:
            api.query('sendChatAction',{'chat_id':origMsg['chat']['id'],'action':'typing'})
            ct = time.time()
    if finalMsg:
        api.sendMessage(origMsg['chat']['id'],finalMsg,{'reply_to_message_id':origMsg['message_id']})

def clearGroup(a,d,g,u):
    'clearGroup - used by checkGroup'
    if d['group'].hasItem(g):
        d['group'].remItem(g)
        print('Automatically removing group '+str(g)+' from group list.')
    try:
        api.query('leaveChat',{'chat_id':g},retry=0)
    except tg.APIError:
        pass

def cu(db,item):
    result = {}
    if int(item) in botconfig.superAdmin:
        return {'status':'super'}
    elif db['admin'].hasItem(str(item)):
        return {'status':'admin','time':int(db['admin'].getItem(str(item),'date'))}
    elif db['noir'].hasItem(str(item)):
        return {'status':'noir','time':int(db['noir'].getItem(str(item),'date')),'comment':db['noir'].getItem(str(item),'comment')}
    elif db['blanc'].hasItem(str(item)):
        return {'status':'blanc','time':int(db['blanc'].getItem(str(item),'date')),'comment':db['blanc'].getItem(str(item),'comment')}
    else:
        return None

def processItem(item,db,api):
    cmdList = ('/ping','/fakeuser','/genuineuser','/authenticuser','/checkuser','/promote','/unlistuser','/cleargroup')
    if 'message' in item:
        if item['message']['chat']['type'] in ('group','supergroup') and not db['group'].hasItem(str(item['message']['chat']['id'])):
            if canSpeak(api,str(item['message']['chat']['id'])):
                print('I am supposed to be in the group '+str(item['message']['chat']['id']))
                db['group'].addItem((str(item['message']['chat']['id']),str(int(time.time()))))
            else: ## Cannot speak
                api.query('leaveChat',{'chat_id':str(item['message']['chat']['id'])})
        if 'text' in item['message'] and len(item['message']['text']) > 1 and item['message']['text'][0] == '/':
            hasToReply = False
            stripText = item['message']['text'].split('\n',1)[0].split(' ',1)[0]
            if len(stripText) > len(api.info['username']) and stripText[-len(api.info['username'])-1:] == '@'+api.info['username']:
                hasToReply = True
                stripText = stripText[:-len(api.info['username'])-1]
            stripText = stripText.lower()
            if stripText in cmdList:
                ## Start processing commands
                if stripText == '/ping':
                    api.sendMessage(item['message']['chat']['id'],'Hell o\'world! It took me '+str(time.time()-item['message']['date'])[:9]+' seconds to receive your message.',{'reply_to_message_id':item['message']['message_id']})
                elif stripText in ('/fakeuser','/genuineuser','/authenticuser'):
                    if db['admin'].hasItem(str(item['message']['from']['id'])) or item['message']['from']['id'] in botconfig.superAdmin:
                        tmp = item['message']['text'].split('\n',1)
                        reason = tmp[1] if len(tmp) == 2 else None
                        tmp = tmp[0].split(' ',2)
                        if len(tmp) == 1 or (reason is None and len(tmp) == 2) or not tmp[1].isdigit():
                            api.sendMessage(item['message']['chat']['id'],'Usage: <pre>'+stripText+' UID Reason</pre>',{'reply_to_message_id':item['message']['message_id']})
                        else:
                            if reason is None:
                                reason = tmp[2]
                            t = cu(db,tmp[1])
                            if t is None:
                                db[('blanc','noir')[stripText=='/fakeuser']].addItem((tmp[1],str(int(time.time())),reason))
                                api.sendMessage(item['message']['chat']['id'],'UID 為 <pre>'+tmp[1]+'</pre> 的<a href="tg://user?id='+tmp[1]+'">用戶</a>已被成功加入'+('可信','仿冒')[stripText=='/fakeuser']+'用戶列表。',{'reply_to_message_id':item['message']['message_id']})
                                if stripText == '/fakeuser' and 'notifyGroup' in botconfig.__dict__ and botconfig.notifyGroup:
                                    api.sendMessage(botconfig.notifyGroup,'<a href="tg://user?id='+tmp[1]+'">仿冒用戶</a>\nUID: <pre>'+tmp[1]+'</pre>\n'+tg.tgapi.escape(reason))
                            else:
                                api.sendMessage(item['message']['chat']['id'],'注意：UID 為 <pre>'+tmp[1]+'</pre> 的<a href="tg://user?id='+tmp[1]+'">用戶</a>已被標記為'+{'super':'超級管理','admin':'管理','noir':'仿冒','blanc':'可信'}[t['status']]+'用戶。如需修改，請先撤銷標記。',{'reply_to_message_id':item['message']['message_id']})
                    else:
                        api.sendMessage(item['message']['chat']['id'],'抱歉，只有濫權管理員才可以將用戶標記為'+('可信','仿冒')[stripText == '/fakeuser']+'用戶。',{'reply_to_message_id':item['message']['message_id']})
                elif stripText == '/checkuser':
                    if len(item['message']['text'].split(' ', 1)) == 1 or not item['message']['text'].split(' ',1)[1].isdigit():
                        target = item['message']['reply_to_message']['forward_from'] if ('reply_to_message' in item['message'] and 'forward_from' in item['message']['reply_to_message']) else item['message']['reply_to_message']['from'] if 'reply_to_message' in item['message'] else item['message']['from']
                    else:
                        target = {'id':item['message']['text'].split(' ', 1)[1],'username':item['message']['text'].split(' ', 1)[1]}
                    result = cu(db,str(target['id']))
                    if result is None:
                        result = '我並沒有關於用戶 '+tg.getNameRep(target) +' 的記錄。'
                    elif result['status'] == 'super':
                        result = '用戶 '+tg.getNameRep(target)+' 是尊貴的超級濫權管理員。'
                    elif result['status'] == 'admin':
                        result = '用戶 '+tg.getNameRep(target)+' 於 '+datetime.datetime.fromtimestamp(result['time']).isoformat()+'Z 成為濫權管理員。'
                    else:
                        result = '用戶 '+tg.getNameRep(target)+' 於 '+datetime.datetime.fromtimestamp(result['time']).isoformat()+'Z 被標記為'+('可信','仿冒')[result['status'] == 'noir']+'用戶。備註：'+tg.tgapi.escape(result['comment'])
                    api.sendMessage(item['message']['chat']['id'],result,{'reply_to_message_id':item['message']['message_id']})
                elif stripText == '/promote':
                    if item['message']['from']['id'] in botconfig.superAdmin or (db['admin'].hasItem(str(item['message']['from']['id'])) and 'op' in db['admin'].getItem(str(item['message']['from']['id']),'flag').split('|')):
                        if 'reply_to_message' in item['message']:
                            tmp = item['message']['text'].split(' ',1)
                            tmp = tmp[1].split('|') if len(tmp) == 2 else []
                            flags = []
                            for i in tmp:
                                if i in flaglist:
                                    flags.append(i)
                            flags = '|'.join(flags)
                            tmp = cu(db,item['message']['reply_to_message']['from']['id'])
                            if tmp is not None:
                                if tmp['status'] == 'super':
                                    api.sendMessage(item['message']['chat']['id'],'用戶 '+tg.getNameRep(item['message']['reply_to_message']['from'])+' 已經是尊貴的超級濫權管理員了。',{'reply_to_message_id':item['message']['message_id']})
                                else:
                                    db[tmp['status']].remItem(str(item['message']['reply_to_message']['from']['id']))
                                    api.sendMessage(item['message']['chat']['id'],'用戶 '+tg.getNameRep(item['message']['reply_to_message']['from'])+' 已自動從'+{'admin':'管理','noir':'仿冒','blanc':'可信'}[tmp['status']]+'用戶列表中移除。',{'reply_to_message_id':item['message']['message_id']})
                                    if tmp['status'] == 'noir' and 'notifyGroup' in botconfig.__dict__ and botconfig.notifyGroup:
                                        api.sendMessage(botconfig.notifyGroup,'<a href="tg://user?id='+u+'">前仿冒用戶</a>\nUID: <pre>'+u+'</pre>\n已自動從仿冒用戶列表中移除。')
                            db['admin'].addItem((str(item['message']['reply_to_message']['from']['id']),str(int(time.time())),flags))
                            api.sendMessage(item['message']['chat']['id'],'用戶 '+tg.getNameRep(item['message']['reply_to_message']['from'])+' 已成功成為濫權管理員。',{'reply_to_message_id':item['message']['message_id']})
                        else:
                            api.sendMessage(item['message']['chat']['id'],'Usage: Reply to the user that would be promoted with <pre>/promote [flags]</pre>',{'reply_to_message_id':item['message']['message_id']})
                    else:
                        api.sendMessage(item['message']['chat']['id'],'抱歉，只有超級濫權管理員才可以設立其他濫權管理員。',{'reply_to_message_id':item['message']['message_id']})
                elif stripText == '/unlistuser':
                    if item['message']['from']['id'] in botconfig.superAdmin or db['admin'].hasItem(str(item['message']['from']['id'])):
                        tmp = item['message']['text'].split(' ',1)
                        if len(tmp) == 1 or (not tmp[1].strip()) or (not tmp[1].isdigit()):
                            api.sendMessage(item['message']['chat']['id'],'Usage: <pre>/unlistuser UID</pre>',{'reply_to_message_id':item['message']['message_id']})
                        else:
                            u = tmp[1]
                            tmp = cu(db,u)
                            if tmp is None:
                                api.sendMessage(item['message']['chat']['id'],'抱歉，我並沒有關於<a href="tg://user?id='+u+'">該用戶</a> (<pre>'+u+'</pre>) 的記錄。',{'reply_to_message_id':item['message']['message_id']})
                            elif tmp['status'] == 'super':
                                api.sendMessage(item['message']['chat']['id'],'<a href="tg://user?id='+u+'">超級濫權管理員</a> (<pre>'+u+'</pre>) 的權力不容侵犯！你的請求被濫權掉了。',{'reply_to_message_id':item['message']['message_id']})
                            elif tmp['status'] in ('noir','blanc') or (tmp['status'] == 'admin' and (item['message']['from']['id'] in botconfig.superAdmin or 'op' in db['admin'].getItem(str(item['message']['from']['id'] in botconfig.superAdmin),'flag').split('|'))):
                                db[tmp['status']].remItem(u)
                                api.sendMessage(item['message']['chat']['id'],'<a href="tg://user?id='+u+'">用戶</a> (<pre>'+u+'</pre>) 已從'+{'admin':'濫權管理','noir':'仿冒','blanc':'可信'}[tmp['status']]+'用戶列表中移除。',{'reply_to_message_id':item['message']['message_id']})
                                if tmp['status'] == 'noir' and 'notifyGroup' in botconfig.__dict__ and botconfig.notifyGroup:
                                    api.sendMessage(botconfig.notifyGroup,'<a href="tg://user?id='+u+'">前仿冒用戶</a>\nUID: <pre>'+u+'</pre>\n已從仿冒用戶列表移除。')
                            else:
                                api.sendMessage(item['message']['chat']['id'],'<a href="tg://user?id='+tmp+'">濫權管理員</a> (<pre>'+tmp+'</pre>) 的權力不容你的侵犯！你的請求被濫權掉了。',{'reply_to_message_id':item['message']['message_id']})
                    else:
                        api.sendMessage(item['message']['chat']['id'],'抱歉，只有濫權管理員才可以移除用戶標記。',{'reply_to_message_id':item['message']['message_id']})
                elif stripText == '/cleargroup':
                    if item['message']['from']['id'] in botconfig.superAdmin or db['admin'].hasItem(str(item['message']['from']['id'])):
                        t = tg.threading.Thread(target=checkGroup,args=(api,db,db['group'].keys(),api.info['id']),kwargs={'origMsg':item['message'],'outgroup':clearGroup,'finalMsg':'已完成清理群組。'})
                        t.start()
                        api.fork.append(t)
                    else:
                        api.sendMessage(item['message']['chat']['id'],'抱歉，只有濫權管理員才可以清理群組列表。',{'reply_to_message_id':item['message']['message_id']})
                else:
                    api.sendMessage(item['message']['chat']['id'],'我本來應該有這功能的，但是好像主人偷懶沒做⋯⋯',{'reply_to_message_id':item['message']['message_id']})
                ## End processing commands
            elif hasToReply:
                api.sendMessage(item['message']['chat']['id'],'請問您對我有什麼奇怪的期待嗎？',{'reply_to_message_id':item['message']['message_id']})
        elif db['noir'].hasItem(str(item['message']['from']['id'])):
            if canPunish(api,item['message']['chat']['id']):
                try:
                    api.query('kickChatMember',{'chat_id':item['message']['chat']['id'],'user_id':item['message']['from']['id'],'until_date':int(time.time()+10)})
                    api.query('deleteMessage',{'chat_id':item['message']['chat']['id'],'message_id':item['message']['message_id']})
                    api.sendMessage(item['message']['chat']['id'],'用戶 '+tg.getNameRep(item['message']['from'])+' 已於 '+datetime.datetime.fromtimestamp(int(db['noir'].getItem(str(item['message']['from']['id']),'date'))).isoformat()+'Z 被標記為仿冒用戶。該用戶已被自動踢出。')
                except tg.APIError:
                    api.sendMessage(item['message']['chat']['id'],'該用戶（'+tg.getNameRep(item['message']['from'])+'）已被標記為仿冒用戶，請各位注意。',{'reply_to_message_id':item['message']['message_id']})
            else:
                api.sendMessage(item['message']['chat']['id'],'該用戶（'+tg.getNameRep(item['message']['from'])+'）已被標記為仿冒用戶，請各位注意。',{'reply_to_message_id':item['message']['message_id']})
        elif 'new_chat_members' in item['message'] and item['message']['chat']['type'] in ('group','supergroup'):
            ## Two thing to do: Check if BL user joins
            ## Check if I join a new group
            for newMember in item['message']['new_chat_members']:
                if newMember['id'] == api.info["id"]:
                    db['group'].addItem((str(item['message']['chat']['id']),str(int(time.time()))))
                elif db['noir'].hasItem(newMember['id']):
                    if canPunish(api,item['message']['chat']['id']):
                        api.query('kickChatMember',{'chat_id':item['message']['chat']['id'],'user_id':newMember['id'],'until_date':int(time.time()+10)})
                        api.sendMessage(item['message']['chat']['id'],'新入群用戶 '+tg.getNameRep(newMember)+' 已於 '+datetime.datetime.fromtimestamp(int(db['noir'].getItem(str(newMember['id']),'date'))).isoformat()+'Z 被標記為仿冒用戶。該用戶已被自動踢出。')
                    else:
                        api.sendMessage(item['message']['chat']['id'],'新入群用戶 '+tg.getNameRep(newMember)+' 已於 '+datetime.datetime.fromtimestamp(int(db['noir'].getItem(str(newMember['id']),'date'))).isoformat()+'Z 被標記為仿冒用戶，請各位注意。')
        elif 'left_chat_member' in item['message'] and item['message']['left_chat_member']['id'] == api.info['id']:
            print('I have been removed from group '+str(item['message']['chat']['id'])+'.')
            if db['group'].hasItem(str(item['message']['chat']['id'])):
                db['group'].remItem(str(item['message']['chat']['id']))

def run(db,api):
    batch = api.query('getUpdates')
    lastID = int(db['config'].getItem('lastid','value'))
    for item in batch:
        if item['update_id'] > lastID:
            db['config'].addItem(('lastid',str(item['update_id'])))
            try:
                processItem(item,db,api)
            except tg.APIError as e:
                if 'message' in item and not canSpeak(api,item['message']['chat']['id']):
                    print('Chat '+str(item['message']['chat']['id'])+' has blocked me. Quitting...')
                    if db['group'].hasItem(str(item['message']['chat']['id'])):
                        db['group'].remItem(str(item['message']['chat']['id']))
                    try:
                        api.query('leaveChat',{'chat_id':item['message']['chat']['id']})
                    except tg.APIError:
                        pass
                print('Error processing the following item:')
                print(item)
            lastID = item['update_id']
        else:
            print('Message '+str(item['update_id'])+' skipped')
    while True:
        batch = api.query('getUpdates',{'offset':lastID+1,'timeout':20}) if lastID is not None else api.query("getUpdates",{'timeout':20})
        for item in batch:
            db['config'].addItem(('lastid',str(item['update_id'])))
            processItem(item,db,api)
            lastID = item['update_id']
        api.clearFork()
        time.sleep(1)

def main():
    dbFile = botconfig.db
    apiKey = botconfig.apiKey
    db = {'config':sqldb.sqliteDB(dbFile,'config')}
    if db['config'].getItem('dbver','value') != '1.0':
        raise tg.APIError('DB','DB Version Mismatch')
    for item in ('noir','blanc','admin','group'):
        db[item] = sqldb.sqliteDB(db['config'],item)
    api = tg.tgapi(apiKey)
    run(db,api)

if __name__ == '__main__':
    main()
