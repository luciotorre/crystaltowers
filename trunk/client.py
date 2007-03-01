from twisted.spread import pb
from twisted.python.failure import Failurefrom twisted.internet import reactor, deferfrom twisted.python import util
import time, sys
import threading
import Queue

class ClientError(Exception): pass

def waitFor(func, *args, **kwargs):
    queue = Queue.Queue()

    def result(*args):
        queue.put(args[0])

    def callable_f():
        d = func(*args, **kwargs)
        d.addCallback(result)
        d.addErrback(result)
        
    reactor.callFromThread(callable_f)
    result = queue.get()
    if isinstance(result, Failure):
        raise ClientError(result.getErrorMessage())
    return result
    
def Error(reason):
    d = defer.Deferred()
    d.errback(reason)
    return d
        
class RemoteBoard(pb.Referenceable):
    def __init__(self):
        self.board = None
        self.pieces = None
        
    def remote_set_board(self, board):
        self.board = board
        
    def remote_set_pieces(self, pieces):
        self.pieces = pieces
        
    def dump(self):
        if not self.board: return
        for where, stack in self.board.items():
            print where, ":","[",
            for p in stack:
                print str(self.pieces[p][1])+self.pieces[p][2],
            print "]"
        sys.stdout.flush()
                
class CrystalClient:
    def __init__(self, server_host, server_port=9091):
        self.server_host = server_host
        self.server_port = server_port
        self.root = None
        self.current_game = None
        
        self.factory = factory = pb.PBClientFactory()

        t = threading.Thread(target=self.reactor_thread)
        t.start()

        
    def connect(self):
        reactor.connectTCP(self.server_host, self.server_port, self.factory)    
        d = self.factory.getRootObject()
        d.addCallback(self.connected)
        d.addCallback(self.setBoard)
        return d
        
    def connected(self, root):
        self.root = root
        return root        
                    
    def setBoard(self, root):
        return root
    
    def reactor_thread(self):
        reactor.run(installSignalHandlers=0)
        
    def connect_error(self, *args):
        self.root = 0

import cmd

class GameCmd(cmd.Cmd):
    def __init__(self, server, username, callback):
        self.server = server
        self.username = username
        self.board = RemoteBoard()
            
        self.current = None
        self.player = None
        cmd.Cmd.__init__(self)
        
    def do_games(self, rest):
        games = waitFor(self.server.callRemote, "games")
        for i, game in enumerate(games):
            print i,":", waitFor(game.callRemote, "name")

            
    def do_create(self, rest):
        if not rest:
            print "create NAME"
            return
        game = waitFor(self.server.callRemote, "create_game", rest)
        player = waitFor(game.callRemote, "join", self.username)
        self.current = game
        self.player = player
        
    def do_players(self, rest):
        if not self.current:
            print "must be in game"
            return
        for name in waitFor(self.current.callRemote, "players"):
            print name
            
    def do_join(self, rest):
        what = int(rest)
        if self.current:
            print "not while inside a game"
            return
        game = waitFor(self.server.callRemote, "games")[ what ]
        self.player = waitFor(game.callRemote, "join", self.username)
        self.current = game
        
    def do_ready(self, rest):
        if not self.current:
            print "must be in game"
            return
        
        waitFor(player.callRemote, "set_board", self.board)
            
        waitFor(self.player.callRemote, "set_ready")
        done = False
        while not done:
            game, players = waitFor(self.current.callRemote, "player_status")
            if game=="STATUS_PLAYER":
                done = True
                break
            print "-"*20
            print "Game Status:", game
            print "Player Status:"
            for pl,st in players:
                print "\t", pl,":", st
            time.sleep(2)
        self.callback(self.server, self.current, self.player, self.board)
        
        
if __name__ == "__main__":
    test = 0
    try:
        if test:
            cl = CrystalClient("127.0.0.1")
    
            board = RemoteBoard()
            server = waitFor(cl.connect)
            game = waitFor(server.callRemote, "create_game", "g")
            player = waitFor(game.callRemote, "sample_game", 4)
            waitFor(player.callRemote, "set_board", board)
            waitFor(player.callRemote, "set_ready")
            waitFor(game.callRemote, "shuffle")
            board.dump()
            time.sleep(100)
        else:
            def fooback(*args):
                print args
                
            name = raw_input("Your name?:")
            ip = raw_input("Server IP? (default localhost):")
            if not ip: ip = "127.0.0.1"
            cl = CrystalClient(ip)
            server = waitFor(cl.connect)
            cmdserver = GameCmd(server, name, fooback)
            cmdserver.cmdloop()
            
    finally:
        reactor.callFromThread(reactor.stop)
        
        
        