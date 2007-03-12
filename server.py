
from twisted.spread import pb
from twisted.internet import reactor
import model

class ServerError(pb.Error):   pass

class NetworkServer(pb.Root):
    def __init__(self):
        self.server = model.Server()
        
    def remote_games(self):
        return [ NetworkGame(g) for g in self.server.games() ]

    def remote_create_game(self, name):
        g = self.server.create_game(name)
        return NetworkGame(g)
        
    
class NetworkGame(pb.Referenceable):
    def __init__(self, game):
        self.game = game
        
    def remote_players(self):
        return [ p.name for p in self.game.players ]

    def remote_player_status(self):
        return (self.game.state_repr(),
                    [ (p.name, p.state_repr()) for p in self.game.players ])
        
    def remote_join(self, name):
        player = self.game.join(name)
        return NetworkPlayer(player)
        
    def remote_name(self):
        return self.game.name
    
    def remote_get_side(self):
        return self.game.board.side
        
    def __repr__(self):
        return "< g:"+self.name+">"
        
    def remote_sample_game(self, num_players):
        players = []
        for i in range(num_players-1):
            p = self.game.join("player %i"%i)
            players.append( p )
            
        player = self.game.join("user")
        for p in players:
            p.set_ready()

        return NetworkPlayer(player)
        
    def remote_shuffle(self):
        if not self.game.status == self.game.STATUS_PLAYING:
            raise ServerError("Cannot Shuffle")
        model.random_moved(self.game)
        
class NetworkPlayer(pb.Referenceable):
    def __init__(self, player):
        self.player = player
        
    def remote_set_board(self, board):
        self.player.remote_board = board
        
    def remote_on_hand(self):
        if self.player.on_hand is None: return None
        return self.player.on_hand.id
    
    def remote_set_ready(self):
        return self.player.set_ready()
              
    def remote_set_wait(self):
        return self.player.set_wait()
        
    def remote_pass_move(self):
        return self.player.pass_move()
            
    def remote_leave(self):
        return self.player.leave()
        
    def remote_pick(self, stack):
        return self.player.pick(stack)
        
    def remote_cap(self, stack):
        return self.player.cap(stack)
            
    def remote_drop(self, where):
        return self.player.drop(where)
        
    def remote_split(self, stack, piece, where):
        piece = self.player.game.board.piece_map[piece]
        return self.player.split(stack, piece, where)
        
    def remote_mine(self, stack, piece):
        piece = self.player.game.board.piece_map[piece]
        return self.player.mine(stack, piece)
        

if __name__ == '__main__':
    reactor.listenTCP(9091, pb.PBServerFactory(
                            NetworkServer()
                        ))
    reactor.run()
