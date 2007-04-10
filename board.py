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
from euclid import *
import selection

class GameError(pb.Error): pass

class RegularPolygonNode(qgl.scene.Leaf):
    def __init__(self, nSides, radius):
        assert nSides >= 3
        self.vertices = []
        for n in range(nSides): #0.0, math.pi*2, math.pi*2/nSides):
            theta = math.pi*2*n/nSides
            self.vertices.append( (math.cos(theta)*radius, 0, math.sin(theta)*radius) )

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

class HexagonNode(RegularPolygonNode):
    def __init__(self, radius):
        RegularPolygonNode.__init__(self, 6, radius)

class TriangleListNode(qgl.scene.Leaf):
    def __init__(self, vertices):
        self.vertices = []

        self.normals = []
        for triangleVertices in vertices:
            v1, v2, v3 = [ Point3(*v) for v in triangleVertices ]
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


class Game:
    server = None
    players = None
    picked = None

    def __init__(self):
        #setup pygame as normal, making sure to include the OPENGL flag in the init function arguments.
        pygame.init()
        flags =  OPENGL|DOUBLEBUF|HWSURFACE
        pygame.display.set_mode(WINDOW_SIZE, flags)

        #Create the visitors.
        #The compiler visitor is used to change a Node object into a set of OpenGL draw commands. More on nodes later.
        self.compiler = qgl.render.Compiler()
        #The render visitor is used to execute compiled commands.
        self.render = qgl.render.Render()
        #the picker visitor can check which attributes are clicked by a mouse
        self.picker = qgl.render.Picker()
        
        #the root node is the root of the tree structure (also called a scene graph). Branches get added to the root. 
        self.root_node = qgl.scene.Root()
        
        #every root node must have a viewport branch, which specifies which area of the screen to draw to.
        #the PersepctiveViewport renders all its children in a 3d view.
        viewport = qgl.scene.PerspectiveViewport()
        viewport.screen_dimensions = (0,0) + WINDOW_SIZE
        
        #a group node can translate, rotate and scale its children. it can also contain leaves, which are drawable things.
        self.gameGroup = qgl.scene.Group()
        #because this group will be displayed in 3d, using a PerspectiveViewport, it makes sense to move it into the screen
        #using the group.translate attribute. Any objects drawn at a depth (z) of 0.0 in a perspective viewport will not be show.
        self.gameGroup.translate = Point3( 0.0, -10.0, -50 )
        #the group node has attributes that can be changed to manipulate the position of its children.
        self.gameGroup.axis = Vector3(0,1,0)
        self.gameGroup.angle = 45
        
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
        self.root_node.add(viewport)
        viewport.add(environment)
        environment.add(light)
        environment.add(self.gameGroup)

        self.localBoard = RemoteBoard()

        self.boardGroup = qgl.scene.Group()
        #boardGroup.axis = (1,0,0)
        #boardGroup.angle -= 90
        self.boardGroup.translate = (0,-1,0)
        #boardTexture = qgl.scene.state.Texture("art/board.jpg")
        #self.boardGroup.add(boardTexture)
        self.gameGroup.add(self.boardGroup)

        #Before the structure can be drawn, it needs to be compiled.
        #To do this, we ask the root node to accept the compiler visitor.
        #If any new nodes are added later in the program, they must also
        #accept the compiler visitor before they can be drawn.
        self.root_node.accept(self.compiler)
        self.pieces = {}
        self.onHand = None
        self.boardPlane = Plane( Point3(0,-11,0), Point3(0,-11,1), Point3(1,-11,1) )

    def setupLoop(self):
        self.loopingCall = task.LoopingCall(self.loop)
        self.loopingCall.start(1.0/FPS)

    def buildBoard(self, side):
        hex = HexagonNode( 2.1 )
        color = (0.2, 0.2, 0.2, 1)
        darkcolor = (0.2, 0.2, 0.2, 1)
        material = qgl.scene.state.Material(specular=color, emissive=darkcolor )
        self.boardGroup.add( material )

        self.localBoard.side = side
        for x in range(side):
            for z in range(side):
                cell = qgl.scene.Group()
                cell.selectable = True
                cell.position = (x,z)
                self.boardGroup.add(cell)

                cell.translate = (x-side/2 + ((z%2)*0.5+0.25))*4, 0, (z-side/2)*3.5777087639996634
                cell.angle = 90
                cell.axis= 0,1,0
                cell.add( hex )

        playerColours = {}
        for n, playerName in enumerate(self.players):
            playerColours[playerName] = TOWER_COLOURS[n]

        pyramidTriangles = [
            [(0,2,0), (-1,-1,-1), (1,-1,-1)],
            [(0,2,0), (1,-1,-1), (1,-1,1)],
            [(0,2,0), (1,-1,1), (-1,-1,1)],
            [(0,2,0), (-1,-1,1), (-1,-1,-1)],
        ]
        pyramidNode = TriangleListNode( pyramidTriangles )

        for (pieceId, (playerName, pieceSize, playerId)) in self.localBoard.pieces.iteritems():
            pyramid = qgl.scene.Group()
            pyramid.id = pieceId
            pyramid.selectable = True
            self.pieces[pieceId] = pyramid

            scale = TOWER_SCALES[pieceSize-1]
            pyramid.scale = [scale]*3

            color = playerColours[playerName]
            darkcolor = (color[0]*0.15, color[1]*0.15, color[2]*0.2, 1.0)
            material = qgl.scene.state.Material(specular=color, emissive=darkcolor )

            pyramid.add(material, pyramidNode)
            self.gameGroup.add(pyramid)

        self.gameGroup.accept(self.compiler)

    def start(self):
        factory = pb.PBClientFactory() 
        reactor.connectTCP("127.0.0.1", 9091, factory)
        d = factory.getRootObject().addCallback(self.gotServer)

    def gotServer(self, server):
        self.server = server
        server.callRemote("create_game", "g").addCallback(self.gotGame)

    def gotGame(self, game):
        self.server.game = game
        game.callRemote("sample_game", 5).addCallback(self.gotPlayer)

    def gotPlayer(self, player):
        self.server.player = player
        player.callRemote("set_board", self.localBoard).addCallback(self.boardSet)

    def boardSet(self, *a):
        self.server.player.callRemote("set_ready").addCallback(self.playerReady)

    def playerReady(self, *a):
        self.server.game.callRemote("shuffle").addCallback(self.boardShuffled)

    def boardShuffled(self, *a):
        self.server.game.callRemote("players").addCallback(self.gotPlayers)

    def gotPlayers(self, plys):
        self.players = plys
        self.server.game.callRemote("get_side").addCallback(self.gotSide)

    def gotSide(self, side):
        self.buildBoard(side)

    lastPosition = None
    #the main render loop
    def loop(self):
        side = self.localBoard.side
        if side is not None:
            # place every piece in their own spot
            board = self.localBoard.board
            for (x,z), stack in board.items():
                y = 0
                lastscale = 0
                for pieceId in stack:
                    piece = self.pieces[pieceId]
                    piece.position = (x,z)
                    piece.stack = stack
                    scale = piece.scale[0]

                    if lastscale != 0:
                        y += 3*(lastscale - scale) + 0.4

                    piece.translate = (x-side/2 + ((z%2)*0.5+0.25))*4, -1+scale + y, (z-side/2)*3.5777087639996634
                    lastscale = scale

        position = pygame.mouse.get_pos()
        self.picked = None
        if position != self.lastPosition:
            self.lastPosition = position
            #tell the picker we are interested in the area clicked by the mouse
            self.picker.set_position(position)
            #ask the root node to accept the picker.
            self.root_node.accept(self.picker)
            #picker.hits will be a list of nodes which were rendered at the position.
            if len(self.picker.hits) > 0:
                self.picked = self.picker.hits[0]
                if self.picked is self.onHand and len(self.picker.hits) > 1:
                    self.picked = self.picker.hits[1]

        #process pygame events.
        for event in pygame.event.get():
            if event.type is QUIT:
                reactor.stop()
            elif event.type is KEYDOWN and event.key is K_ESCAPE:
                reactor.stop()
            elif event.type is MOUSEMOTION:
                if self.onHand is not None:
                    #print self.onHand.id, event.pos
                    #x, y, z = self.onHandTranslate
                    ray = selection.generateSelectionRay(*event.pos)
                    point = self.boardPlane.intersect(ray)
                    if point is not None:
                        matrix = Matrix4.new_rotate_axis(-math.radians(self.gameGroup.angle), self.gameGroup.axis).translate(*-self.gameGroup.translate)
                        point = matrix * point
                        #x, y, z = Point3(*point)-Point3(*self.gameGroup.translate)
                        x, y, z = point
                        self.onHand.translate = x, 0, z
                    print "feel my death ray...", event.pos, ray, point
                    
            elif event.type is MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.picked is not None:
                        if hasattr(self.picked, "id"):
                            if self.localBoard.on_hand is None:
                                def gotPiece(result, piece):
                                    print "Fue levantada la pieza...", piece
                                    self.onHand = piece
                                    #self.onHandTranslate = piece.translate
                                def noPiece(failure, *a):
                                    print failure, failure.getErrorMessage(), failure.type, a
                                    self.onHand = None
                                    raise failure
                                    # failure.trap...
                                self.server.player.callRemote("pick", self.picked.position).addCallbacks(gotPiece, errback=noPiece, callbackArgs=[self.picked])
                            else:
                                self.server.player.callRemote("cap", self.picked.position)
                        elif hasattr(self.picked, "position"):
                            self.server.player.callRemote("drop", self.picked.position)
                            self.onHand = None
                elif event.button == 4:
                    self.gameGroup.angle -= 5
                    self.lastPosition = None
                elif event.button == 5:
                    self.gameGroup.angle += 5
                    self.lastPosition = None


        #ask the root node to accept the render visitor.
        #This will draw the structure onto the screen.
        #notice that QGL draws everything from the centre, and
        #that the 0,0 point in a QGL screen is the center of the screen.
        self.root_node.accept(self.render)
        pygame.display.flip()


if __name__ == "__main__":
    game=Game()
    game.setupLoop()
    game.start()
    reactor.run()
    pygame.quit()
