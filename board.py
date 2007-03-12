from __future__ import division
import pygame
import random
from pygame.locals import *

import qgl
from OpenGL.GL import *
from OpenGL.GLU import *
    
from twisted.internet import reactor
from twisted.spread import pb
from twisted.internet import task

from client import RemoteBoard
import math
import euclid

class HexagonNode(qgl.scene.Leaf):
    def __init__(self, r):
        s=math.sin(math.radians(60))*r
        self.vertices = (0,0,0), (r,0,0), (r/2,0,s), (-r/2,0,s), (-r,0,0), (-r/2,0,-s), (r/2,0,-s), (r,0,0)

    def compile(self):
        self.list = qgl.render.GLDisplayList()
        glNewList(self.list.id, GL_COMPILE)
        glBegin(GL_TRIANGLE_FAN)
        glNormal3dv( (0.0, 0.0, -1.0) )
        for vertices in self.vertices:
            glVertex3dv(vertices)
        glEnd()
        glEndList()

    def execute(self):
        glCallList(self.list.id)

class TriangleListNode(qgl.scene.Leaf):
    def __init__(self, vertices):
        self.vertices = []

        self.normals = []
        for triangleVertices in vertices:
            v1, v2, v3 = [ euclid.Point3(*v) for v in triangleVertices ]
            normal=(v3-v2).cross(v2-v1).normalized()
            self.normals.append(normal)
            self.vertices.append(triangleVertices)

    def compile(self):
        self.list = qgl.render.GLDisplayList()
        glNewList(self.list.id, GL_COMPILE)
        glBegin(GL_TRIANGLES)
        for normal, vertices in zip(self.normals, self.vertices):
            glNormal3dv(normal)
            for v in vertices:
                glVertex3dv(v)
        glEnd()
        glEndList()

    def execute(self):
        glCallList(self.list.id)


TOWER_COLOURS = [
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 0.8, 0.0, 1.0),
    (0.3, 0.3, 1.0, 1.0),
    (1.0, 1.0, 0.0, 1.0),
    (0.3, 0.8, 0.5, 1.0),
    (0.8, 0.3, 1.0, 1.0),
]
TOWER_SCALES = [ 0.4, 0.7, 1 ]
FPS=30
WINDOW_SIZE=(800,600)


def main():
    #setup pygame as normal, making sure to include the OPENGL flag in the init function arguments.
    pygame.init()
    flags =  OPENGL|DOUBLEBUF|HWSURFACE
    pygame.display.set_mode(WINDOW_SIZE, flags)

    #Create the visitors.
    #The compiler visitor is used to change a Node object into a set of OpenGL draw commands. More on nodes later.
    compiler = qgl.render.Compiler()
    #The render visitor is used to execute compiled commands.
    render = qgl.render.Render()
    #the picker visitor can check which attributes are clicked by a mouse
    picker = qgl.render.Picker()
    
    #the root node is the root of the tree structure (also called a scene graph). Branches get added to the root. 
    root_node = qgl.scene.Root()
    
    #every root node must have a viewport branch, which specifies which area of the screen to draw to.
    #the PersepctiveViewport renders all its children in a 3d view.
    viewport = qgl.scene.PerspectiveViewport()
    viewport.screen_dimensions = (0,0) + WINDOW_SIZE
    
    #a group node can translate, rotate and scale its children. it can also contain leaves, which are drawable things.
    group = qgl.scene.Group()
    #because this group will be displayed in 3d, using a PerspectiveViewport, it makes sense to move it into the screen
    #using the group.translate attribute. Any objects drawn at a depth (z) of 0.0 in a perspective viewport will not be show.
    group.translate = ( 0.0, -10.0, -50 )
    #the group node has attributes that can be changed to manipulate the position of its children.
    group.axis = (0,1,0)
    group.angle = 45
    
    pyramidTriangles = [
        [(0,2,0), (-1,-1,-1), (1,-1,-1)],
        [(0,2,0), (1,-1,-1), (1,-1,1)],
        [(0,2,0), (1,-1,1), (-1,-1,1)],
        [(0,2,0), (-1,-1,1), (-1,-1,-1)],
    ]
    pyramidNode = TriangleListNode( pyramidTriangles )

    #a Light leaf will control the lighting of any leaves rendered after it.
    light = qgl.scene.state.Light(position=(0,10,20))

    #lets give the light a red hue
    light.diffuse = ( 1.0, 1.0, 1.0, 0.0 )

    #if the light leaf is added to the same group as the children it is going
    #to light, it would move, and rotate with its children.
    #this is not the effect we want in this case, so we add the light to its
    #own group, which we will call environment.
    environment = qgl.scene.Group()

    #Now we add the different nodes and leaves into a tree structure using the .add method. 
    root_node.add(viewport)
    viewport.add(environment)
    environment.add(light)
    environment.add(group)

    localBoard = RemoteBoard()

    boardGroup = qgl.scene.Group()
    #boardGroup.axis = (1,0,0)
    #boardGroup.angle -= 90
    boardGroup.translate = (0,-1,0)
    #texture = qgl.scene.state.Texture("art/board.jpg")
    #boardGroup.add(texture)
    group.add(boardGroup)

    #Before the structure can be drawn, it needs to be compiled.
    #To do this, we ask the root node to accept the compiler visitor.
    #If any new nodes are added later in the program, they must also
    #accept the compiler visitor before they can be drawn.
    root_node.accept(compiler)
    
    pieces = {}
    def buildBoard(localBoard, boardGroup, side):
        hex = HexagonNode( 2.1 )
        color = (0.2, 0.2, 0.2, 1)
        darkcolor = (0.2, 0.2, 0.2, 1)
        material = qgl.scene.state.Material(specular=color, emissive=darkcolor )
        boardGroup.add( material )

        localBoard.side = side
        for x in range(side):
            for z in range(side):
                cell = qgl.scene.Group()
                cell.selectable = True
                cell.position = (x,z)
                boardGroup.add(cell)

                cell.translate = (x-side/2 + ((z%2)*0.5+0.25))*4, 0, (z-side/2)*3.5777087639996634
                cell.angle = 90
                cell.axis= 0,1,0
                cell.add( hex )

        playerColours = {}
        for n, playerName in enumerate(players):
            playerColours[playerName] = TOWER_COLOURS[n]

        for (pieceId, (playerName, pieceSize, playerId)) in localBoard.pieces.iteritems():
            pyramid = qgl.scene.Group()
            pyramid.id = pieceId
            pyramid.selectable = True
            pieces[pieceId] = pyramid

            scale = TOWER_SCALES[pieceSize-1]
            pyramid.scale = [scale]*3

            color = playerColours[playerName]
            darkcolor = (color[0]*0.15, color[1]*0.15, color[2]*0.2, 1.0)
            material = qgl.scene.state.Material(specular=color, emissive=darkcolor )

            pyramid.add(material, pyramidNode)
            group.add(pyramid)

        group.accept(compiler)

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
        game.callRemote("sample_game", 5).addCallback(gotPlayer)
    def gotPlayer(player):
        server.player = player
        player.callRemote("set_board", localBoard).addCallback(boardSet)
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
        buildBoard(localBoard, boardGroup, side)

    factory = pb.PBClientFactory() 
    reactor.connectTCP("127.0.0.1", 9091, factory)
    d = factory.getRootObject().addCallback(gotServer)
    
    global lastPosition, lastSelected, piece
    piece = None
    lastPosition = None
    lastSelected = None
    #the main render loop
    def loop():
        global lastPosition, lastSelected, piece
        side = localBoard.side
        if side is not None:
            # place every piece in their own spot
            board = localBoard.board
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

                    piece.translate = (x-side/2 + ((z%2)*0.5+0.25))*4, -1+scale + y, (z-side/2)*3.5777087639996634
                    lastscale = scale
            
        position = pygame.mouse.get_pos()
        if position != lastPosition:
            lastPosition = position
            #tell the picker we are interested in the area clicked by the mouse
            picker.set_position(position)
            #ask the root node to accept the picker.
            root_node.accept(picker)
            #picker.hits will be a list of nodes which were rendered at the position.
            if len(picker.hits) > 0:
                picked = picker.hits[0]

        #process pygame events.
        for event in pygame.event.get():
            if event.type is QUIT:
                reactor.stop()
            elif event.type is KEYDOWN and event.key is K_ESCAPE:
                reactor.stop()
            elif event.type is MOUSEBUTTONDOWN:
                if event.button == 1:
                    if len(picker.hits) > 0:
                        picked = picker.hits[0]
                        if hasattr(picked, "id"):
                            if localBoard.on_hand is None:
                                def gotPiece(*p):
                                    print "Fue levantada la pieza...", picked
                                def noPiece(failure):
                                    print failure, failure.getErrorMessage(), failure.type
                                    # failure.trap...
                                server.player.callRemote("pick", picked.position).addCallbacks(gotPiece, noPiece)
                            else:
                                server.player.callRemote("cap", picked.position)
                                
                        elif hasattr(picked, "position"):
                            server.player.callRemote("drop", picked.position)
                elif event.button == 4:
                    group.angle -= 5
                elif event.button == 5:
                    group.angle += 5


        #ask the root node to accept the render visitor.
        #This will draw the structure onto the screen.
        #notice that QGL draws everything from the centre, and
        #that the 0,0 point in a QGL screen is the center of the screen.
        root_node.accept(render)
        pygame.display.flip()

    loopingCall = task.LoopingCall(loop)
    loopingCall.start(1.0/FPS)
    reactor.run()
    pygame.quit()

if __name__ == "__main__":
    main()
