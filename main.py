import os
import glob
import pickle
import logging
import threading

from flask import Flask, request, jsonify
from FileReader import FileReader
from Config import Config
from ScriptSpliter import ScriptSpliter


class Game(object):
    def __init__(self, config, chatid):
        self.config = config
        fileReader = FileReader(self.config.filename)
        scriptParser = ScriptSpliter(fileReader)
        self.__gameBlocks = scriptParser.parse()
        self.__gameParameter = {}
        self.chatid=chatid
        self.blockName=""
        self.awaitingOptions = {}
        self.lock = threading.Lock()

    def awaitingOption(self, incom=""):
        with self.lock:
            if incom in self.awaitingOptions:
                result = self.awaitingOptions[incom]
                self.awaitingOptions={}
                print(incom+" => "+result)
                return result
            else:
                print(incom+" Ignored.")
                return None

    def savestate(self):
        with self.lock:
            state={}
            state["blockname"]=      self.blockName
            state["gameParameter"]=  self.__gameParameter
            state["awaitingOptions"]=self.awaitingOptions
            with open('save/'+ str(self.chatid) + '.pkl', 'wb') as f:
                pickle.dump(state, f, pickle.HIGHEST_PROTOCOL)

    def loadstate(self):
        with self.lock:
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

    def run(self, blockName="Start"):
        self.blockName = blockName
        self.savestate()
        while (self.blockName != 'game null pointer' and
                self.blockName != 'awaiting answer'):
            self.blockName, self.__gameParameter, self.awaitingOptions = \
                self.__gameBlocks[self.blockName].execute(
                    self.__gameParameter,self.chatid)
            print("Blockname: ["+self.blockName+"]")
            self.savestate()


class GameServer(Flask):
    def __init__(self, *args, **kwargs):
        super(GameServer, self).__init__(*args, **kwargs)
        self.game_config = Config()
        self.games = self.loadsavefiles()
        self.lock = threading.Lock()

    def loadsavefiles(self):
        games = {}
        for savefile in glob.glob("save/*.pkl"):
            chat_id = int(os.path.splitext(os.path.basename(savefile))[0])
            print("loading: {0}".format(chat_id))
            game = Game(self.game_config, chat_id)
            game.loadstate()
            games[chat_id] = game
        return games

    def process_message(self, msg):
        chat_id = msg.get('chat').get('id')
        incom = msg.get('text')
        print("{0}: {1}".format(chat_id, incom))

        handler = None  # tuple (function, argument)
        if incom.startswith("/start"):
            handler = self.cmd_start, (chat_id,)
        elif incom.startswith("/restart"):
            handler = self.cmd_restart, (chat_id,)
        elif incom.startswith("/jumptoblock"):
            blockname = incom.split(" ", 2)[1]
            handler = self.cmd_jumptoblock, (chat_id, blockname)
        else:
            handler = self.cmd_next_block, (chat_id, incom)

        fun, args = handler
        try:
            fun(*args)
        except Exception as e:
            logging.error(
                "Something went wrong in Playing Id '{0}': {1}".format(
                    chat_id, str(e)))

    def cmd_start(self, chat_id):
        with self.lock:
            if chat_id in self.games:
                print("Game with Playing ID '{0}' is already running.".format(
                    chat_id))
                return

            print("Starting new game. Playing ID: '{0}'".format(chat_id))
            game = self.games[chat_id] = Game(self.game_config, chat_id)
        game.run("Start")

    def cmd_restart(self, chat_id):
        with self.lock:
            if chat_id not in self.games:
                print("Game with Playing ID '{0}' is not running.".format(
                    chat_id))
                return

            print("Restarting Game with Playing ID: {0}".format(chat_id))
            del self.games[chat_id]
            game = self.games[chat_id] = Game(self.game_config, chat_id)
        game.run("Start")

    def cmd_jumptoblock(self, chat_id, blockname):
        with self.lock:
            if chat_id not in self.games:
                print("Game with Playing ID '{0}' is not running.".format(
                    chat_id))
                return
            game = self.games[chat_id]

        print("Jumping to Blockname '{0}'. Playing ID: '{1}'".format(
            blockname, chat_id))
        game.run(blockname)

    def cmd_next_block(self, chat_id, incom):
        with self.lock:
            if chat_id not in self.games:
                print("Game with Playing ID '{0}' is not running.".format(
                    chat_id))
                return
            game = self.games[chat_id]

        nextBlock = game.awaitingOption(incom)
        if nextBlock is not None:
            game.run(nextBlock)

app = GameServer(__name__)


@app.route("/", methods=['POST'])
def webhook():
    """Called by telegram"""
    if request.json is None:
        logging.info("Got unexpected message. Drop it.")
        return 'ok'

    msg = request.json.get('message', None)
    if msg and msg.get('text'):
        t = threading.Thread(target=app.process_message, args=(msg,))
        t.daemon = True
        t.start()
    return 'ok'


@app.route("/stats")
def stats():
    with app.lock:
        return jsonify({
            'num_games': len(app.games),
            'games': [
                {
                    'id': chat_id,
                    'block': game.blockName,
                    'awaiting': game.awaitingOptions
                }
                for chat_id, game in app.games.items()],
            'num_threads': threading.active_count()
        })


def main():
    if not os.path.exists('save'):
        os.mkdir('save')

    context = ('certs/public.pem', 'certs/ds_private.key')
    if not all(map(os.path.exists, context)):
        logging.warning(
            "Certificate(s) not exists. Server will run in http-mode and "
            "won't be able to communicate with Telegram.")
        context = None

    app.run(
        host='0.0.0.0',
        port=8080,
        ssl_context=context,
        threaded=True,
        debug=True)

if __name__ == "__main__":
    main()
