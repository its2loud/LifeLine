import time
import re
from Config import Config
import requests
import json

TOKEN = "XXXXXXXXXXX:YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY"

def sendmessage(text, chatid):
    message = {'chat_id': chatid, 
               'text': text,
               'reply_markup':'{"hide_keyboard": true}'
               }
    requests.post('https://api.telegram.org/bot' + TOKEN + '/sendMessage', data=message)

def timeDelay_Seconds(timeDelay):
    delay=2.5
    try:
        if timeDelay=="norm":
            delay=2.5
        elif "s" in str(timeDelay):
            delay = int(timeDelay.replace("s",""))
        elif "m" in str(timeDelay):
            delay = int(timeDelay.replace("m",""))*60
        elif "h" in str(timeDelay):
            delay = int(timeDelay.replace("h",""))*3600
        else:
            delay = int(timeDelay)
    except Exception as e:
        print("Error parsing timeDelay: "+str(e))
    return delay

class GameBlock:
    def __init__(self, name):
        self.name = name
        self.scripts = []
        self.nextName = 'game null pointer'
        self.__jumpNow = False
        self.__if = [True]
        self.__silently = False
        self.__choicesJump = []
        self.__choicesShow = []
        self.__choices = 0
        self.script_buffer=""

    def __doChoice(self, script):
        tagStart = script.find('[[')
        tagPipe = script.find('|')
        tagEnd = script.find(']]')
        key = script[tagPipe + 1:tagEnd].strip()
        value = script[tagStart + 2:tagPipe].strip()
        self.__choicesJump.append(key)
        self.__choicesShow.append(value)
        self.__choices += 1

    def __doIf(self, script):
        parameter = self.__parameter
        script = script.replace('<<if', '')
        script = script.replace('<<elseif', '')
        script = script.replace('>>', '')
        script = script.replace(' is ', ' == ')
        script = script.replace(' eq ', ' == ')
        script = script.replace(' gte ', ' >= ')
        script = re.sub(r'\$(\S+)', r'parameter["\1"]', script)
        script = script.strip()
        judgeResult = eval(script)
        if Config.debug:
            Config.debugPrint(script)
            Config.debugPrint(judgeResult)

        self.__if[-1] = judgeResult

    def __doElse(self, script):
        self.__if[-1] = not self.__if[-1]

    def __doEndIf(self, script):
        self.__if.pop()

    def __doJudge(self, script):
        if script.startswith('<<if'):
            self.__if.append(True)
            self.__doIf(script)
            return
        if script.startswith('<<elseif'):
            self.__doIf(script)
            return
        if script.startswith('<<endif'):
            self.__doEndIf(script)
            return
        if script.startswith('<<else'):
            self.__doElse(script)
            return

    def __doJump(self, chatid, script):
        if script.startswith('[[delay'):
            pipPosition = script.find('|')
            self.nextName = script[pipPosition + 1:-2]
            delay_by_script = script[7:pipPosition]
            print("Delay by Script: "+delay_by_script)
            if self.script_buffer!="":
                    self.__delay(chatid)
                    sendmessage(self.script_buffer,chatid)
                    self.script_buffer=""
            self.__delay(chatid, timeDelay=delay_by_script, busy=True)
        else:
            self.nextName = script[2:-2]
        if Config.debug:
            Config.debugPrint(self.nextName)
        self.__jumpNow = True

    def __doSet(self, script):
        parameter = self.__parameter
        script = script.replace('<<set ', '')
        script = script.replace('>>', '')
        script = re.sub(r'\$(\S+)', r'parameter["\1"]', script)
        script = script.strip()
        exec(script)
        if Config.debug:
            Config.debugPrint(script)
        self.__parameter = parameter

    def __doSilently(self, script):
        self.__silently = script.startswith('<<silently')

    def __doPrintParameter(self, script):
        tagStart = script.find('$')
        tagEnd = script.find('>>')
        parameter = script[tagStart + 1:tagEnd]
        try:
            parameter = self.__parameter[parameter]
        except:
            parameter = ''
        print('\b%s' % parameter, end='')

    def __doScript(self, chatid, script):
        if script.startswith('<<if') or script.startswith('<<elseif') or \
                script.startswith('<<endif') or script.startswith('<<else'):
            self.__doJudge(script)
            return
        if self.__if[-1]:
            if script.startswith('[['):
                self.__doJump(chatid, script)
                return
            if script.startswith('<<silently') or script.startswith('<<silently'):
                self.__doSilently(script)
                return
            if script.startswith('<<choice'):
                self.__doChoice(script)
                return
            if script.startswith('<<set'):
                self.__doSet(script)
                return
            if script.startswith('<<$'):
                self.__doPrintParameter(script)
                return

    def __makeChoice(self, message, chatid):
        self.__delay(chatid)
        print("MAKE CHOICE")
        keyboard = []    
        awaitingOptions = {}
        for i in range(0, self.__choices):
            keyboard_line = []        
            awaitingOptions[self.__choicesShow[i]]=self.__choicesJump[i]
            keyboard_line.append(self.__choicesShow[i])
            keyboard.append(keyboard_line)
        print(json.dumps(keyboard))
        message = { 'chat_id': chatid, 
                    'text': message,
                    'reply_markup': '{"keyboard": '+json.dumps(keyboard)+', "one_time_keyboard":true, "resize_keyboard":true}'
                  }
        requests.post('https://api.telegram.org/bot' + TOKEN + '/sendMessage', data=message)
        return awaitingOptions

    def __delay(self, chatid, timeDelay="norm", busy=False):
        delay = timeDelay_Seconds(timeDelay)
        if Config.debug:
            delay = 0
        if busy:
            sendmessage('[...ist beschäftigt.]',chatid)
        timeout = time.time() + delay
        while time.time() < timeout:
            time.sleep(.5)

    def execute(self, parameter, chatid):
        self.script_buffer=""
        if Config.debug:
            Config.debugPrint(self.name)
        self.__parameter = parameter
        awaitingOptions = {}
        for script in self.scripts:
            if Config.pause:
                Config.debugPause()
            if script.startswith('<<') or script.startswith('[['):
                self.__doScript(chatid, script)
                if self.__choices == 2:
                    if self.script_buffer!="":
                        question=self.script_buffer
                        self.script_buffer=""
                    else:
                        question="Auswahl："
                    awaitingOptions = self.__makeChoice(question, chatid)
                    self.nextName = "awaiting answer"
                    break
                continue
            if self.__if[-1]:
                if self.script_buffer!="":
                    self.__delay(chatid)
                    sendmessage(self.script_buffer,chatid)
                    self.script_buffer=""
                self.script_buffer=script

            if self.__jumpNow:
                break
        if self.script_buffer!="":
            self.__delay(chatid)
            sendmessage(self.script_buffer,chatid)
        return self.nextName, self.__parameter, awaitingOptions
