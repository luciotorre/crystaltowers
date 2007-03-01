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
        
    def reactor_thread(self):        reactor.run(installSignalHandlers=0)
        
    def connect_error(self, *args):
        self.root = 0

        
        
if __name__ == "__main__":
    cl = CrystalClient("127.0.0.1")
    try:
        board = RemoteBoard()
        server = waitFor(cl.connect)
        game = waitFor(server.callRemote, "create_game", "g")
        player = waitFor(game.callRemote, "sample_game", 4)
        waitFor(player.callRemote, "set_board", board)
        waitFor(player.callRemote, "set_ready")
        waitFor(game.callRemote, "shuffle")
        board.dump()
        time.sleep(100)
    finally:
        reactor.callFromThread(reactor.stop)
        
        
        