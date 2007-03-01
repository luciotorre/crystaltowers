import random, math, string
import unittest

class GameError(Exception): pass

class Piece:
    def __init__(self, player, size, id):
        self.id = id
        self.player = player
        self.size = size
        
    def __repr__(self):
        return "%i%s"%(self.size, self.player.code)

        
class Board:
    """
    .side : board is side x side big
    
    you can iterate over the board or get for each position
    board[(x,y)]
    and get a stack 
    """
    def __init__(self, players):
        self.players = players
        self.positions = {}
        self.piece_map = {}
        
        toset = [ (player, size) 
                    for player in players
                    for size in (1,2,3)
                    for amount in range(5)
                    ]
        random.shuffle(toset)
        pieces = len(toset)
        side = int(math.ceil(math.sqrt(pieces*1.3)))
        self.side = side
        empty_positions = [ (x,y) 
                            for x in range(side) 
                            for y in range(side)
                         ]
        
        piece_count = 0
        for player, size in toset:
            position = random.choice(empty_positions)
            piece = Piece(player, size, piece_count)
            self.place(position, piece)
            self.piece_map[piece_count]=piece
            piece_count += 1
            empty_positions.remove(position)
            
    def dump(self):
        total = 0
        count = 0
        print "Stacks:"
        
        for where, stack in self.positions.items():
            print where, ":", stack
            total += len(stack)
            count += 1
            
        print "Pieces:", total
        print "Stacks:", count
        
    def __getitem__(self, key):
        return self.positions.get(key, None)
        
    def __setitem__(self, key, value):
        self.positions[key] = value
        
    def __iter__(self):
        return self.positions.iteritems()
        
    def __delitem__(self, key):
        del self.positions[key]
        
    def __contains__(self, key):
        return key in self.positions
           
    def place(self, position, piece):
        if not position in self.positions or self.positions[position] is None:
            self.positions[position]=[piece]
        else:
            stack = self.positions[position]
            if stack[-1].player == piece.player:
                raise GameError("Cannot place over your pieces")
            if stack[-1].size < piece.size:
                raise GameError("Cannot place over smaller pieces")
        
            stack.append( piece )
                    
    def pick(self, where, piece):
        if not where in self.positions:
            raise GameError("Cannot pick from nowhere")
        
        stack = self.positions[where]
        
        if not piece in stack:
            raise GameError("Piece not there to pick up")
            
        stack.remove(piece)
        
        if not stack:
            del self.positions[where]
        
        return piece
            
    def split(self, where_from, piece, where_to):
        #print "%"*200
        #self.dump()
        stack_from = self.positions[where_from]
        pos = stack_from.index(piece)
        self.positions[where_to] = stack_from[pos:]
        self.positions[where_from] = stack_from[:pos]
        #print "*"*200
        #self.dump()
        #print "-"*100
   
        
            
       
class Server:
    def __init__(self):
        self._games = []
        
    def games(self):
        return self._games
        
    def create_game(self, name):
        game = Game(name, self)
        self._games.append(game)
        return game
            
    def kill(self, game):
        if game in self._games:
            self._games.remove(game)
        
class StateMixin:
    def make_states(self):
        self._state_map = {}
        states = [ s.strip() for s in self.states.split("\n") ]
        for num, state in enumerate(states):
            self._state_map[num]=state
            setattr(self, state, num)
            
    def state_repr(self):
        return self._state_map[self.status]
        
    def __repr__(self):
        return "<%s: state == %s>"%(self.__class__.__name__, self.state_repr())
        
class Game(StateMixin):
    states = """
        STATUS_WAITING
        STATUS_PLAYING
        STATUS_DONE
        """

    def __repr__(self):
        return "<%s:%s: state == %s>"%(self.__class__.__name__, self.name, self.state_repr())
            
    def __init__(self, name, server):
        self.make_states()
        self.server = server
        self.status = self.STATUS_WAITING
        self.name = name
        self.players = []
        self.board = None
        self.winner = None
        self.pending_send = 0
        
    def join(self, name):
        if self.status == self.STATUS_WAITING:
            player = Player(name, self)
            self.players.append( player )
            return player
        else:
            raise GameError("Cannot join ongoing game")        
    
    def check_ready(self):
        if not self.status == self.STATUS_WAITING:
            return False
            
        ready = sum([ 1 for p in self.players if p.status == p.STATUS_READY ])
        print "players ready:", ready, "of", len(self.players)
        if ready != len(self.players):
            return False
                    
        for p in self.players:
            p.status = p.STATUS_PLAYING
            self.status = self.STATUS_PLAYING
            self.board = Board(self.players)
            
        for i,p in enumerate(self.players):
            p.code = string.lowercase[i]
        self.send_all()
        return True
        
    def check_done(self):
        if self.status == self.STATUS_WAITING:
            return False
        if self.status == self.STATUS_DONE:
            return True
            
        if self.status == self.STATUS_PLAYING:
            for p in self.players:
                if not p.status in (p.STATUS_BLOCKED, p.STATUS_PASS, p.STATUS_LEFT):
                    return False
                    
        #todo: count scores

        self.players = [ p for p in self.players 
                            if p.status != p.STATUS_LEFT ]
                
        for p in self.players:
            p.status = p.STATUS_DONE
        self.status = self.STATUS_DONE
        
        return True
        
    def left(self, player):
        if self.status == self.STATUS_WAITING:
            if player in self.players:
                self.players.remove(player)
        else:
            allgone = True
            for p in self.players:
                if p.status != p.STATUS_LEFT:
                    allgone = False
            if allgone:
                self.status = self.STATUS_DONE
                self.server.kill(self)
             
    def send_all(self):
        board_map = self.get_board_map()
        pieces_map = self.get_piece_map()
        
        for p in self.players:
            if p.remote_board:
                d = p.remote_board.callRemote("set_pieces", pieces_map)
                d = p.remote_board.callRemote("set_board", board_map)
       
    def moved(self):
        board_map = self.get_board_map()
        
        for p in self.players:
            if p.remote_board:
                self.pending_send += 1
                print "Queue for", p.name
                d = p.remote_board.callRemote("set_board", board_map)
                d.addCallback(self.sent)
                
    def sent(self, *args):
        self.pending_send -= 1
        #print "sent!, pending =", self.pending_send
                
                
    def get_board_map(self):
        result = {}
        for location, stack in self.board:
            result[location] = [ p.id for p in stack ]
            
        return result
        
    def get_piece_map(self):
        result = {}
        for id, piece in self.board.piece_map.items():
            result[id]=(piece.player.name, piece.size, piece.player.code)
        return result
        
    
class Player(StateMixin):
    states = """
        STATUS_WAIT
        STATUS_READY
        STATUS_PLAYING
        STATUS_BLOCKED
        STATUS_PASS
        STATUS_DONE
        STATUS_LEFT
        """
  
    
    def __repr__(self):
        return "<%s:%s: state == %s>"%(self.__class__.__name__, self.name, self.state_repr())
    
    def __init__(self, name, game):
        self.make_states()
        self.status = self.STATUS_WAIT
        self.name = name
        self.game = game
        self.on_hand = None
        self.remote_board = None
    
    def set_ready(self):
        if self.status in (self.STATUS_READY, self.STATUS_WAIT):
            self.status = self.STATUS_READY
            self.game.check_ready()
        else:
            raise GameError("Cannot get ready")
            
    def set_wait(self):
        if self.status in (self.STATUS_READY, self.STATUS_WAIT):
            self.status = self.STATUS_WAIT
        else:
            raise GameError("Cannot go waiting")
    
    def pass_move(self):
        if self.on_hand is not None:
            raise GameError("Cannot pass while holding a piece")
        if self.status in (self.STATUS_PLAYING, self.STATUS_BLOCKED, self.STATUS_PASS):
            self.status = self.STATUS_PASS
            self.game.check_done()
        else:
            raise GameError("Cannot go waiting")
            
    def leave(self):
        self.status = self.STATUS_LEFT
        self.game.left(self)
        
    def pick(self, where):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if self.on_hand is not None:
            raise GameError("Cannot hold two pieces")
            
        stack = self.game.board[where]
        if len(stack) != 1:
            raise GameError("Canot pick from stack with many pieces")
        if stack[0].player != self:
            raise GameError("Cannot pick another players pieces")
        piece = self.game.board.pick(where, stack[0])
        self.on_hand = piece    
        self.game.moved()
        
    def cap(self, where):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if self.on_hand is None:
            raise GameError("Cannot cap without a piece")
            
        self.game.board.place(where, self.on_hand)
        self.on_hand = None
        self.game.moved()
            
    def drop(self, where):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if self.on_hand is None:
            raise GameError("Nothing to drop")
            
        stack = self.game.board[where]
        
        if stack is None:
            self.game.board.place(where, self.on_hand)
            self.on_hand = None
            self.game.moved()
            return True
        else:
            raise GameError("Cannot drop, there are pieces there already") 
        
        
    def split(self, where_from, piece, where_to):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
            
        stack = self.game.board[where_from]
        
        if len([ p for p in stack if p.player == self ]) < 2:
            raise GameError("Need two or more pieces to split")
        if not piece in stack:
            raise GameError("Piece is not There") 
            
        pos = stack.index(piece)
        if pos == 0:
            raise GameError("cannot split from bottom piece")
        if not stack[pos-1].player == self:
            raise GameError("The piece below must be yours to split")
            
        new_stack = self.game.board[where_to]
        if new_stack is not None:
            raise GameError("Cant place on busy tile")
        
        self.game.board.split(where_from, piece, where_to)
        
        self.game.moved()        
        
    def mine(self, where, piece):
        if self.on_hand is not None:
            raise GameError("Cannot hold two pieces")
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
            
        stack = self.game.board[where]
        
        if not piece in stack:
            raise GameError("Piece is not There")
        if stack[-1].player == self:
            raise GameError("Cannot mine a tower you own")
            
        if len([ p for p in stack if p.player == self ]) < 2:
            raise GameError("Need two or more pieces to mine")
            
        self.on_hand = piece
        self.game.board.pick(where, piece)
        self.game.moved()
        
    
### UTITLITY ##

def game_for(num_players):
    server = Server()
    game = server.create_game("the game")      
    players = []
    for i in range(num_players):
        p = game.join("player %i"%i)
        players.append ( p )
        
    for p in players:
        p.set_ready()
    return game
    
def random_moved(game):
    g = game
    g.board.dump()
    
    side = g.board.side
    positions = [ (x,y) for x in range(side) for y in range(side) ]
    for where in positions:
        if where in g.board and len(g.board[where])==1:
            p = g.board[where][0].player
            p.pick(where)
            capped = False
            for where_to in positions:
                if where_to!=where:
                    try:
                        p.cap(where_to)
                        capped = True
                    except GameError, e:
                        pass
            if not capped:
                p.drop(where)
            else:
                pass#break 
        
       
    print "cap all"
    g.board.dump()
        
    print "mine all"
    for where in positions:
        s = g.board[where]
        if s and len(s) > 3:
            for piece in s:
                pl = piece.player
                mined = False
                try:
                    pl.mine(where, piece)
                    mined = True
                except GameError:
                    pass
                if mined:
                    for k in [ (x,y) 
                            for x in range(g.board.side) 
                            for y in range(g.board.side) ]:
                        try:
                            pl.drop(k)
                            #break
                        except GameError:
                            pass
    g.board.dump()    
    #return g
    print "readytosplit"
    for where in positions:
        s = g.board[where]
        splat = False
        if s and len(s) > 3:
            for piece in s:
                pl = piece.player
                for k in [ (x,y) 
                        for x in range(g.board.side) 
                        for y in range(g.board.side) ]:
                    try:
                        pl.split(where, piece, k)
                        splat = True
                        break
                    except GameError, e:
                        pass
        #if splat: break
        #break
                    
    print "split all"
    g.board.dump()
    
    return g
    
### TESTS ###

class TestLoginOut(unittest.TestCase):  
    def setUp(self):
        self.server = Server()
          
    def testall(self):
        server = self.server
        self.assertEqual( server.games(), [])
        server.create_game("one")      
        server.create_game("two")
        server.create_game("three")    
        
        self.assertEqual( len(server.games()), 3 )
        game = server.games()[2]
        self.assertEqual(game.status, game.STATUS_WAITING)
        p1 = game.join("p1")
        p2 = game.join("p2")
        p3 = game.join("p3")
        p4 = game.join("p4")
        
        players = [p1, p2, p3, p4]
        
        for p in players:
            p.set_ready()
            
        self.assertEqual(game.status, game.STATUS_PLAYING)
        
        for p in players:
            p.pass_move()
        
        self.assertEqual(game.status, game.STATUS_DONE)
        
        for p in players:
            p.leave()
    
        self.assertEqual( len(server.games()), 2 )
        
    def testutil(self):
        game = game_for(5)

if __name__ == "__main__":
    unittest.main()
    
    server = Server()
    
    