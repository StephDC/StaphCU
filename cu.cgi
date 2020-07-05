#! /usr/bin/env python3
import cgi
import datetime
import json
import os
import sqldb
import sys
import xml.dom.minidom as md

import botconfig

__ver__ = '1.0'
metList = {}
htmlhead = lambda x:'''<!DOCTYPE html>
<html>
\t<head>
\t\t<meta charset="UTF-8" />
\t\t<title>StaphCU API - '''+x+'''</title>
\t</head>
\t<body>
\t\t<h1>StaphCU API - '''+x+'''</h1>'''
htmlbottom = '''\t\t<footer>
\t\t\t<small>&copy;Copyleft '''+str(datetime.date.today().year)+', <i>Staph. aureus</i> | API Version: <code>'+__ver__+'''</code><br />Source code available at <a href="https://github.com/StephDC/StaphCU">https://github.com/StephDC/StaphCU</a></small>
\t\t</footer>
\t</body>\n</html>'''

class cgiFBargv():
    def __init__(self):
        self.k = cgi.FieldStorage()
        self.met = self.k.getvalue('met')
        if self.met is None:
            if len(sys.argv) < 2:
                raise KeyError('unspecified method')
            self.met = sys.argv[1]
        if self.met not in metList:
            raise KeyError('unsupported method')
    def getvalue(self,key):
        tmp = None
        if key in metList[self.met]['args']:
            tmp = self.k.getvalue(key)
            if tmp is None:
                try:
                    tmp = sys.argv[metList[self.met]['args'].index(key)+2]
                    if tmp == 'None':
                        tmp = None
                except IndexError:
                    tmp = None
            elif tmp == '':
                tmp = None
            elif type(tmp) is list:
                tmp = tmp[0]
        return tmp

def printCU(cudata,f):
    toName = {'noir':'Fake','blanc':'Authentic','admin':'Admin','super':'SuperAdmin','unknown':'Unknown'}
    cudata['status'] = toName[cudata['status']]
    if f is None or f == 'text':
        print('Content-Type: text/plain; charset=UTF-8')
        status = cudata.pop('status')
        for item in cudata:
            print('X-CU-'+item.upper()+': '+cudata[item])
        print('\n'+status)
    elif f == 'json':
        print('Content-Type: application/json\n')
        print(json.dumps(cudata))
    elif f == 'xml':
        print('Content-Type: text/xml\n')
        tr = md.Element('user')
        for item in cudata:
            tc = md.Element(item)
            tt = md.Text()
            tt.data = cudata[item]
            tc.appendChild(tt)
            tr.appendChild(tc)
        print(tr.toprettyxml(indent='\t').strip())
    elif f == 'psv':
        print('Content-Type: text/csv; charset=UTF-8\n')
        print('|'.join(cudata.keys()))
        print('|'.join(cudata.values()))
    else:
        print('Content-Type: text/plain; charset=UTF-8\n')
        print('Error: unsupported format')

# checkUser provides 'cu'
def checkUser(stdin):
    db = {'noir':sqldb.sqliteDB(botconfig.db,'noir')}
    for item in ('blanc','admin'):
        db[item] = sqldb.sqliteDB(db['noir'],item)
    cuid = stdin.getvalue('uid')
    if cuid is None:
        result = {'status':'error','comment':'uid is not specified'}
    else:
        result = {'uid':cuid}
        if int(cuid) in botconfig.superAdmin:
            result['status'] = 'super'
        else:
            for item in ('noir','blanc','admin'):
                if db[item].hasItem(cuid):
                    result['status'] = item
                    result['time'] = db[item].getItem(cuid,'date')
                    if item != 'admin':
                        result['comment'] = db[item].getItem(cuid,'comment')
                    break
        if 'status' not in result:
            result['status'] = 'unknown'
    printCU(result,stdin.getvalue('format'))

metList['cu'] = {
        'args':('uid','format'),
        'intro':'Check user',
        'help':'Required Args:\n\tuid - TG User ID\n\nOptional Args:\n\tformat - "text" or "json" or "xml" or "psv"',
        'function':checkUser
}
# 'cu' provided

# apiInfo provides 'ver'
def apiInfo(stdin):
    f = stdin.getvalue('format')
    if f == 'html':
        print('Content-Type: text/html\n')
        print(htmlhead('ver'))
        print('\t\t<p>API Version: '+__ver__+'</p>')
        print(htmlbottom)
    elif f is None or f == 'text':
        print('Content-Type: text/plain; charset=UTF-8\n')
        print(__ver__)
    else:
        print('Content-Type: text/plain; charset=UTF-8\n')
        print('Error: unsupported format')

metList['ver'] = {
        'args':('format',),
        'intro':'Print API version',
        'help':'Optional Args:\n\tformat - "text" or "html"',
        'function':apiInfo
}
# 'ver' provided

# apiHelp provides 'help'
def apiHelp(stdin):
    f = stdin.getvalue('format')
    if f is not None and f not in ('text','html'):
        print('Content-Type: text/plain; charset=UTF-8\n')
        print('Error: unsupported format')
        return
    if f == 'html':
        print('Content-Type: text/html\n')
        print(htmlhead('help'))
        print('\t\t<pre>')
    else:
        print('Content-Type: text/plain; charset=UTF-8\n')
    target = stdin.getvalue('helpmet')
    if target is None:
        print('Available methods:')
        for item in metList:
            print('\t'+item+' - '+metList[item]['intro'])
        print('\nSpecify helpmet to get more info.')
    elif target in metList:
        print(target+' - '+metList[target]['intro']+'\n')
        print('All Args: '+' '.join(metList[target]['args'])+'\n')
        print(metList[target]['help'])
    else:
        print('Error: unsupported method')
    if f == 'html':
        print('\t\t</pre>')
        if target is None:
            print('\t\t<form method="GET" action="'+os.environ['SCRIPT_NAME']+'">\n\t\t\t<input type="hidden" name="met" value="help" />')
            print('\t\t\t<label for="helpmet">helpmet: </label>\n\t\t\t<select id="helpmet" name="helpmet">')
            for item in metList:
                print('\t\t\t\t<option value="'+item+'">'+item+'</option>')
            print('\t\t\t</select>')
            print('\t\t\t<input type="hidden" name="format" value="html" />\n\t\t\t<input type="submit" />')
            print('\t\t</form>')
        elif target in metList:
            print('\t\t<form method="POST" action="'+os.environ['SCRIPT_NAME']+'">\n\t\t\t<input type="hidden" name="met" value="'+target+'" />')
            for item in metList[target]['args']:
                print('\t\t\t<label for="'+item+'">'+item+'</label><input type="text" id="'+item+'" name="'+item+'" /><br />')
            print('\t\t\t<input type="submit" />\n\t\t</form>')
        print(htmlbottom)

metList['help'] = {
        'args':('helpmet','format'),
        'intro':'Get help for this API',
        'help':'Optional Args:\n\thelpmet - the met you need help with\n\tformat - "text" or "html"',
        'function':apiHelp
}
# 'help' provided

def main():
    try:
        stdin = cgiFBargv()
    except KeyError as e:
        print('Content-Type: text/plain; charset=UTF-8\n')
        print('Error: '+e.args[0])
        exit()
    met = stdin.met
    if met in metList:
        metList[met]['function'](stdin)

if __name__=='__main__':
    main()
