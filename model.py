import random, math
import unittest

class GameError(Exception): pass

class Piece:
    def __init__(self, player, size):
        self.player = player
        self.size = size
    
class Stack:
    def __init__(self, where):
        self.position = where
        self.pieces = []
        
    def place(self, piece):
        if self.pieces:
            if self.pieces[-1].player == piece.player:
                raise GameError("Cannot place over your pieces")
            if self.pieces[-1].size < piece.size:
                raise GameError("Cannot place over smaller pieces")
        
        self.pieces.append(piece)
        
    def pop(self):
        return self.pieces.pop()
        
    def size(self):
        return len(self.pieces)
    
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
        
        for player, size in toset:
            position = random.choice(empty_positions)
            piece = Piece(player, size)
            self.place(piece, position)
            empty_positions.remove(position)
            
    def __getitem__(self, key):
        return self.positions.get(key, None)
        
    def __setitem__(self, key, value):
        self.positions[key] = value
        
    def __iter__(self):
        return self.positions.itervalues()
        
    def __delitem__(self, key):
        del self.positions[key]
           
    def place(self, piece, position):
        if not position in self.positions:
            stack = Stack( position )
            self.positions[position]=stack
        else:
            stack = self.positions[ position ]
        stack.place( piece )
            
       
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
        self._players = []
        self.board = None
        self.winner = None
        
    def join(self, name):
        if self.status == self.STATUS_WAITING:
            player = Player(name, self)
            self._players.append( player )
            return player
        else:
            raise GameError("Cannot join ongoing game")        
    
    def check_ready(self):
        if not self.status == self.STATUS_WAITING:
            return False
            
        for p in self._players:
            if not p.status == p.STATUS_READY:
                return False
        
        for p in self._players:
            p.status = p.STATUS_PLAYING
            self.status = self.STATUS_PLAYING
            self.board = Board(self._players)
        return True
        
    def check_done(self):
        if self.status == self.STATUS_WAITING:
            return False
        if self.status == self.STATUS_DONE:
            return True
            
        if self.status == self.STATUS_PLAYING:
            for p in self._players:
                if not p.status in (p.STATUS_BLOCKED, p.STATUS_PASS, p.STATUS_LEFT):
                    return False
                    
        #todo: count scores

        self._players = [ p for p in self._players 
                            if p.status != p.STATUS_LEFT ]
                
        for p in self._players:
            p.status = p.STATUS_DONE
        self.status = self.STATUS_DONE
        
        return True
        
    def left(self, player):
        if self.status == self.STATUS_WAITING:
            if player in self._players:
                self._players.remove(player)
        else:
            allgone = True
            for p in self._players:
                if p.status != p.STATUS_LEFT:
                    allgone = False
            if allgone:
                self.status = self.STATUS_DONE
                self.server.kill(self)
                
    def check_blocked(self):
        pass
                
        
    
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
        
    def pick(self, stack):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if self.on_hand is not None:
            raise GameError("Cannot hold two pieces")
        if stack.size() != 1:
            raise GameError("Canot pick from stack with many pieces")
        if stack.pieces[0].player != self:
            raise GameError("Cannot pick another players pieces")
        piece = stack.pop()
        self.on_hand = piece      
        self.game.check_blocked()
        
    def cap(self, stack):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if self.on_hand is None:
            raise GameError("Cannot cap without a piece")
        stack.place(self.on_hand)
        self.on_hand = None
        self.game.check_blocked()
            
    def drop(self, where):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if self.on_hand is None:
            raise GameError("Nothing to drop")
        stack = self.game.board[where]
        if stack is None:
            self.game.board.place(self.on_hand, where)
            self.on_hand = None
            return True
        
        if stack.size() != 0:
            raise GameError("Cannot drop, there are pieces there already") 
            
        self.cap(stack)
        return True
        
        
    def split(self, stack, piece, where):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if len([ p for p in stack.pieces if p.player == self ]) < 2:
            raise GameError("Need two or more pieces to split")
        
            
    def mine(self, stack, piece):
        if self.status != self.STATUS_PLAYING:
            raise GameError("Cannot Move, wrong status")
        if not piece in stack:
            raise GameError("Piece is not There")
        if stack[-1].player == self:
            raise GameError("Cannot mine a tower you own")
        if len([ p for p in stack.pieces if p.player == self ]) < 2:
            raise GameError("Need two or more pieces to mine")
        self.on_hand = piece
        stack.pieces.remove(piece)
        
    
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
    
    