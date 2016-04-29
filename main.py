from flask import Flask, request, session
import ssl
from FileReader import FileReader
from Config import Config
from ScriptSpliter import ScriptSpliter
from GameBlock import GameBlock
import pickle
import glob
import os
import threading

Games = {}

app = Flask(__name__)

class Game:
    def __init__(self, config, chatid):
        self.config = config
        fileReader = FileReader(self.config.filename)
        scriptParser = ScriptSpliter(fileReader)
        self.__gameBlocks = scriptParser.parse()
        self.__gameParameter = {}
        self.chatid=chatid
        self.blockName=""
        self.awaitingOptions = {}

    def awaitingOption(self,incom=""):
        if incom in self.awaitingOptions:
            result = self.awaitingOptions[incom]
            self.awaitingOptions={}
            print(incom+" => "+result)
            return result
        else:
            print(incom+" Ignored.")
            return "None"

    def savestate(self):
        state={}
        state["blockname"]=      self.blockName
        state["gameParameter"]=  self.__gameParameter
        state["awaitingOptions"]=self.awaitingOptions
        with open('save/'+ str(self.chatid) + '.pkl', 'wb') as f:
            pickle.dump(state, f, pickle.HIGHEST_PROTOCOL)

    def loadstate(self):
        with open('save/'+ str(self.chatid) + '.pkl', 'rb') as f:
            state = pickle.load(f)
        self.blockName=      state["blockname"]
        self.__gameParameter=state["gameParameter"]
        self.awaitingOptions=state["awaitingOptions"]    
        if self.blockName != 'game null pointer' and self.blockName != 'awaiting answer':
            print("Reloading Blockname: "+self.blockName)
            self.awaitingOptions={}
            self.run(self.blockName)
        else:
            print("Not reloading Blockname: "+self.blockName)
            print(self.awaitingOptions)

    def run(self,blockName="Start"):
        self.blockName=blockName
        self.savestate()
        while self.blockName != 'game null pointer' and self.blockName != 'awaiting answer':
            self.blockName, self.__gameParameter, self.awaitingOptions = self.__gameBlocks[self.blockName].execute(self.__gameParameter,self.chatid)
            print("Blockname: ["+self.blockName+"]")
            self.savestate()

def process_message(msg):
    chat_id = msg.get('chat').get('id')
    incom = msg.get('text')
    print(str(chat_id)+": "+incom)
    global Games
    if incom[:6] == "/start":
        print("Starting new game. Playing ID: '"+str(chat_id)+"'")
        if not (chat_id in Games):
            Games[chat_id] = Game(config,chat_id)
            Games[chat_id].run("Start")
        else:
            print("Game with Playing ID '"+str(chat_id)+"' is already running.")
    else:
        if chat_id in Games:
            nextBlock = Games[chat_id].awaitingOption(str(incom))
            if nextBlock != "None":
                Games[chat_id].run(nextBlock)
        else:
            print("Game with Playing ID '"+str(chat_id)+"' not found.")
    return "true"

def loadsavefiles():
    global Games
    for savefile in glob.glob("save/*.pkl"):
        chat_id = int(os.path.splitext(os.path.basename(savefile))[0])
        print("loading: "+str(chat_id))
        Games[chat_id] = Game(config,chat_id)
        t = threading.Thread(target=Games[chat_id].loadstate)
        t.daemon = True
        t.start()

@app.route("/", methods=['POST'])
def webhook():
   msg = request.json.get('message')
   if msg and msg.get('text'):
        t = threading.Thread(target=process_message, args=(msg,))
        t.daemon = True
        t.start()
   return 'ok'

config = Config()
loadsavefiles()
if __name__ == "__main__":
    context = ('/PATH/public.pem', '/PATH/private.key')
    app.run(
        host='0.0.0.0',
        port=XX,
        ssl_context=context,
        threaded=True,
        debug=False)