from __future__ import division
import pygame
import random
from pygame.locals import *

try:
    import pygame.fastevent as eventmodule
except ImportError:
    import pygame.event as eventmodule

import qgl
from OpenGL.GL import *
from OpenGL.GLU import *
    
from twisted.internet import threadedselectreactor
threadedselectreactor.install()
from twisted.internet import reactor
from twisted.spread import pb

from client import RemoteBoard
import math

TWISTEDEVENT = USEREVENT

def postTwistedEvent(func):
    # if not using pygame.fastevent, this can explode if the queue
    # fills up.. so that's bad.  Use pygame.fastevent, in pygame CVS
    # as of 2005-04-18.
    eventmodule.post(eventmodule.Event(TWISTEDEVENT, iterateTwisted=func))

class Hexagon(qgl.scene.Leaf):
    def __init__(self, r):
        s=math.sin(math.radians(60))*r
        self.vertices = (0,0,0), (r,0,0), (r/2,0,s), (-r/2,0,s), (-r,0,0), (-r/2,0,-s), (r/2,0,-s), (r,0,0)

    def compile(self):
        lst = qgl.render.GLDisplayList()
        glNewList(lst.id, GL_COMPILE)
        glBegin(GL_TRIANGLE_FAN)
        glNormal3dv( (0.0, 0.0, -1.0) )
        for vertices in self.vertices:
            glVertex3dv(vertices)
        glEnd()
        glEndList()
        self.list = lst

    def execute(self):
        glCallList(self.list.id)


TOWERCOLOURS = [
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 0.8, 0.0, 1.0),
    (0.3, 0.3, 1.0, 1.0),
    (1.0, 1.0, 0.0, 1.0),
    (0.3, 0.8, 0.5, 1.0),
    (0.8, 0.3, 1.0, 1.0),
]
TOWERSCALES = [ 0.4, 0.7, 1 ]


def main():
    #setup pygame as normal, making sure to include the OPENGL flag in the init function arguments.
    pygame.init()
    if hasattr(eventmodule, 'init'):
        eventmodule.init()
    
    flags =  OPENGL|DOUBLEBUF|HWSURFACE
    pygame.display.set_mode((800,600), flags)

    # send an event when twisted wants attention
    reactor.interleave(postTwistedEvent)
    # make shouldQuit a True value when it's safe to quit
    # by appending a value to it.  This ensures that
    # Twisted gets to shut down properly.
    shouldQuit = []
    reactor.addSystemEventTrigger('after', 'shutdown', shouldQuit.append, True)
    
    #Create two visitors.
    #The compiler visitor is used to change a Node object into a set of OpenGL draw commands. More on nodes later.
    compiler = qgl.render.Compiler()
    #The render visitor is used to execute compiled commands.
    render = qgl.render.Render()
    #the picker visitor can check which attributes are clicked by a mouse
    picker = qgl.render.Picker()
    
    #the root node is the root of the tree structure (also called a scene graph). Branches get added to the root. 
    root_node = qgl.scene.Root()
    
    #every root node must have a viewport branch, which specified which area of the screen to draw to.
    #the PersepctiveViewport renders all its children in a 3d view.
    viewport = qgl.scene.PerspectiveViewport()
    viewport.screen_dimensions = (0,0,800,600)
    
    #a group node can translate, rotate and scale its children. it can also contain leaves, which are drawable things.
    group = qgl.scene.Group()
    #because this group will be displayed in 3d, using a PerspectiveViewport, it makes sense to move it into the screen
    #using the group.translate attribute. Any objects drawn at a depth (z) of 0.0 in a perspective viewport will not be show.
    group.translate = (0.0,-10.0,-50)
    
    towerTriangles = [
        [(0,2,0), (-1,-1,-1), (1,-1,-1)],
        [(0,2,0), (1,-1,-1), (1,-1,1)],
        [(0,2,0), (1,-1,1), (-1,-1,1)],
        [(0,2,0), (-1,-1,1), (-1,-1,-1)],
    ]
    tria = qgl.scene.state.TriangleList( towerTriangles )

    #a Light leaf will control the lighting of any leaves rendered after it.
    light = qgl.scene.state.Light(position=(0,10,20))

    #lets give the light a red hue
    light.diffuse = ( 1.0, 1.0, 1.0, 0.0 )

    #if the light leaf is added to the same group as the children it is going to light, it would move, and rotate with its children.
    #this is not the effect we want in this case, so we add the light to its own group. which we will call environment.
    environment = qgl.scene.Group()

    #Now we add the different nodes and leaves into a tree structure using the .add method. 
    root_node.add(viewport)
    viewport.add(environment)
    environment.add(light)
    environment.add(group)

#    cl = client.CrystalClient("127.0.0.1")
    remoteBoard = RemoteBoard()
    try:
#        server = client.waitFor(cl.connect)
#        print client.waitFor(server.callRemote,"games")
#        game = client.waitFor(server.callRemote, "create_game", "g")
#        player = client.waitFor(game.callRemote, "sample_game", 4)
#        players = client.waitFor(game.callRemote, "players")
#        client.waitFor(player.callRemote, "set_board", remoteBoard)
#        client.waitFor(player.callRemote, "set_ready")
#        client.waitFor(game.callRemote, "shuffle")
#        boardSide = client.waitFor(game.callRemote, "get_side")
#        remoteBoard.dump()
        pass
    finally:
#        client.reactor.callFromThread(client.reactor.stop)
        pass

    #game = model.random_moved(4) # model.game_for(4)

    #for player, color in zip(game.players, TOWERCOLOURS):
    #    player.color = color

    boardGroup = qgl.scene.Group()
    #boardGroup.axis = (1,0,0)
    #boardGroup.angle -= 90
    boardGroup.translate = (0,-1,0)
    #texture = qgl.scene.state.Texture("art/board.jpg")
    #boardGroup.add(texture)
    group.add(boardGroup)
    #Before the structure can be drawn, it needs to be compiled. To do this, we ask the root node to accept the compiler visitor.
    #If any new nodes are added later in the program, they must also accept the compiler visitor before they can be drawn.
    root_node.accept(compiler)
    
    pieces = {}
    def buildBoard(remoteBoard, boardGroup):
        color = (0.2, 0.2, 0.2, 1)
        darkcolor = (0.2, 0.2, 0.2, 1)
        material = qgl.scene.state.Material(specular=color, emissive=darkcolor )
        boardGroup.add( material )

        board = remoteBoard.board
        hex = Hexagon( 2.1 )
        for x in range(remoteBoard.side):
            for z in range(remoteBoard.side):
                cell = qgl.scene.Group()
                cell.selectable = True
                cell.position = (x,z)
                boardGroup.add(cell)

                cell.translate = (x-remoteBoard.side/2 + ((z%2)*0.5+0.25))*4, 0, (z-remoteBoard.side/2)*3.5777087639996634
                cell.angle = 90
                cell.axis= 0,1,0
                #quad = qgl.scene.state.Quad( (4, 3.5777087639996634) )
                cell.add( hex )

        playerColours = {}
        for n, playerName in enumerate(players):
            playerColours[playerName] = TOWERCOLOURS[n]

        for (pieceId, (playerName, pieceSize, playerId)) in remoteBoard.pieces.iteritems():
            pyramid = qgl.scene.Group()
            pyramid.id = pieceId
            pyramid.selectable = True
            pieces[pieceId] = pyramid

            scale = TOWERSCALES[pieceSize-1]
            pyramid.scale = [scale]*3

            color = playerColours[playerName]
            darkcolor = (color[0]*0.15, color[1]*0.15, color[2]*0.2, 1.0)
            material = qgl.scene.state.Material(specular=color, emissive=darkcolor )

            pyramid.add(material, tria)
            group.add(pyramid)

        boardGroup.accept(compiler)

    global server
    server = None
    global players
    players = None
    def gotServer(srv):
        global server
        server = srv
        server.callRemote("create_game", "g").addCallback(gotGame)
    def gotGame(game):
        global server
        server.game = game
        game.callRemote("sample_game", 4).addCallback(gotPlayer)
    def gotPlayer(player):
        server.player = player
        player.callRemote("set_board", remoteBoard).addCallback(boardSet)
    def boardSet(*a):
        server.player.callRemote("set_ready").addCallback(playerReady)
    def playerReady(*a):
        server.game.callRemote("shuffle").addCallback(boardShuffled)
    def boardShuffled(*a):
        server.game.callRemote("players").addCallback(gotPlayers)
    def gotPlayers(plys):
        global players
        players = plys
        server.game.callRemote("get_side").addCallback(gotSide)
    def gotSide(side):
        remoteBoard.side = side
        buildBoard(remoteBoard, boardGroup)

    factory = pb.PBClientFactory() 
    reactor.connectTCP("127.0.0.1", 9091, factory)
    d = factory.getRootObject().addCallback(gotServer)
    
    clock = pygame.time.Clock()

    piece = None
    #the main render loop
    lastPosition = None
    lastSelected = None
    while True:
        if remoteBoard.side is not None:
            # place every piece in their own spot
            board = remoteBoard.board
            for (x,z), stack in board.items():
                y = 0
                lastscale = 0
                for pieceId in stack:
                    piece = pieces[pieceId]
                    piece.position = (x,z)
                    piece.stack = stack
                    scale = piece.scale[0]

                    if lastscale != 0:
                        y += 3*(lastscale - scale) + 0.4

                    piece.translate = (x-remoteBoard.side/2 + ((z%2)*0.5+0.25))*4, -1+scale + y, (z-remoteBoard.side/2)*3.5777087639996634
                    lastscale = scale
            
        position = pygame.mouse.get_pos()
        if position != lastPosition:
            lastPosition = position
            #tell the picker we are interested in the area clicked by the mouse
            picker.set_position(position)
            #ask the root node to accept the picker.
            root_node.accept(picker)
            #picker.hits will be a list of nodes which were rendered at the position.
            #to visualise which node was clicked, lets adjust its angle by 10 degrees.
            if len(picker.hits) > 0:
                picked = picker.hits[0]

        #process pygame events.
        for event in eventmodule.get():

            if event.type == TWISTEDEVENT:
                event.iterateTwisted()
                if shouldQuit:
                    return
            if event.type is QUIT:
                reactor.stop()
            elif event.type is KEYDOWN and event.key is K_ESCAPE:
                reactor.stop()
            elif event.type is MOUSEBUTTONDOWN:
                if len(picker.hits) > 0:
                    picked = picker.hits[0]
                    print picked
                    #picked.angle += 10
                    if hasattr(picked, "id"):
                        if remoteBoard.on_hand is None:
                            try:
                                def gotPiece(p):
                                    piece = p
                                    print picked, piece
                                #client.reactor.callFromThread(player.callRemote, "pick", picked.position, picked.id)
                                server.player.callRemote("pick", picked.position).addCallback(gotPiece)
                                #picked.angle += 10
                            except Exception, e:
                                print e
                                pass
                        else:
                            try:
                                pass
                                server.player.callRemote("cap", picked.position)
                            except model.GameError, e:
                                print e
                                pass
                            
                    elif hasattr(picked, "position"):
                        try:
                            server.player.callRemote("drop", picked.position)
                        except Exception, e:
                            print e
                            pass

        #the group node has attributes that can be changed to manipulate the position of its children.
        #if we change the groups axis attribute to (0,1,0), it will rotate on its vertical axis, which is what a planet would probably do.
        group.axis = (0,1,0)
        #group.angle += .5

        #ask the root node to accept the render visitor. This will draw the structure onto the screen.
        #notice that QGL draws everything from the centre, and that the 0,0 point in a QGL screen is the center of the screen.
        root_node.accept(render)
        
        clock.tick(30)
        #flip the display
        pygame.display.flip()


main()
pygame.quit()
