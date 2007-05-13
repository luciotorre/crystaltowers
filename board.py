from __future__ import division
import pygame
import random
from pygame.locals import *

import qgl
import leafs
from OpenGL.GL import *
from OpenGL.GLU import *
    
from twisted.internet import reactor
from twisted.spread import pb
from twisted.internet import task

from client import RemoteBoard
import math
from euclid import *
import selection

SHUFFLE_THE_BOARD = False

class GameError(pb.Error): pass

class RegularPolygonNode(qgl.scene.Leaf):
    def __init__(self, nSides, radius):
        assert nSides >= 3
        self.vertices = []
        for n in range(nSides):
            theta = math.pi*2*n/nSides
            self.vertices.append( (math.cos(theta)*radius, 0, math.sin(theta)*radius) )

    def compile(self):
        self.list = qgl.render.GLDisplayList()
        glNewList(self.list.id, GL_COMPILE)
        glBegin(GL_TRIANGLE_FAN)
        glNormal3dv( (0.0, 1.0, 0.0) )
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


class Menu(qgl.scene.Group):
    selectedItem = None
    menuitemSeparation = 40
    def __init__(self):
        qgl.scene.Group.__init__(self)
        self.node_type = "Group"

    def setOptions(self, menuOptions):
        self.remove(*self.branches)

        numOptions = len(menuOptions)

        fondo = qgl.scene.state.Quad((500, self.menuitemSeparation * numOptions + 20))
        blend = qgl.scene.state.Color( (.05, .05, .3, .8) )
        fondoGroup = qgl.scene.Group()
        fondoGroup.add(blend)
        fondoGroup.add(fondo)
        self.add( fondoGroup )

        self.menuItemsGroup = qgl.scene.Group()
        self.add(self.menuItemsGroup)

        for n, (label, action) in enumerate(menuOptions):
            texto = leafs.TextoAlineado(label, "data/fonts/menu.ttf", size=750, aligny=0.3)
            t = qgl.scene.Group()
            t.action = action
            t.selectable = True
            t.translate = 0, self.menuitemSeparation*(numOptions/2-n-.7), 0
            t.add(texto)
            self.menuItemsGroup.add(t)

    def clicked(self):
        if self.selectedItem is not None:
            print "doing...", self.selectedItem, self.selectedItem.action
            self.selectedItem.action()

    def selected(self, item):
        if item != self.selectedItem:
            if item is not None:
                item.scale = (1.3, 1.3, 1.0)
            if self.selectedItem is not None:
                self.selectedItem.scale = (1.0, 1.0, 1.0)
            self.selectedItem = item


TOWER_COLOURS = [
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 0.8, 0.0, 1.0),
    (0.3, 0.3, 1.0, 1.0),
    (1.0, 1.0, 0.0, 1.0),
    (0.3, 0.8, 0.5, 1.0),
    (0.8, 0.3, 1.0, 1.0),
]
TOWER_SCALES = [ 0.4, 0.7, 1 ]
FPS=15
WINDOW_SIZE=(800,600)


class Game:
    server = None
    players = None
    picked = None
    lastMenuPosition = None

    def __init__(self):
        #setup pygame as normal, making sure to include the OPENGL flag in the init function arguments.
        pygame.init()
        flags =  OPENGL|DOUBLEBUF|HWSURFACE
        #pygame.display.gl_set_attribute(GL_DEPTH_SIZE, 24)
        pygame.display.set_mode(WINDOW_SIZE, flags)
        for f in "GL_ALPHA_SIZE, GL_DEPTH_SIZE, GL_STENCIL_SIZE, GL_ACCUM_RED_SIZE, GL_ACCUM_GREEN_SIZE, GL_ACCUM_BLUE_SIZE, GL_ACCUM_ALPHA_SIZE, GL_MULTISAMPLEBUFFERS, GL_MULTISAMPLESAMPLES, GL_STEREO".split(", "):
            try:
                val = pygame.display.gl_get_attribute(eval(f))
                print f, val
            except:
                pass

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
        self.viewport = qgl.scene.PerspectiveViewport()
        self.viewport.screen_dimensions = (0,0) + WINDOW_SIZE

        self.menuViewport = qgl.scene.OrthoViewport()
        self.menuViewport.screen_dimensions = (0,0) + WINDOW_SIZE
        self.menuDisable()
        
        #a group node can translate, rotate and scale its children. it can also contain leaves, which are drawable things.
        self.gameGroup = qgl.scene.Group()
        #because this group will be displayed in 3d, using a PerspectiveViewport, it makes sense to move it into the screen
        #using the group.translate attribute. Any objects drawn at a depth (z) of 0.0 in a perspective viewport will not be show.
        self.gameGroup.translate = Point3( 0.0, -10.0, -50 )
        #the group node has attributes that can be changed to manipulate the position of its children.
        self.gameGroup.axis = Vector3(0,1,0)
        self.gameGroup.angle = 33
        
        #a Light leaf will control the lighting of any leaves rendered after it.
        ambient = [0.0, 0.0, 0.0, 1.0]
        diffuse = [1.0, 1.0, 1.0, 1.0]
        specular = [1.0, 1.0, 1.0, 1.0]
        position = [0.0, 3.0, 3.0, 0.0]
        light = qgl.scene.state.Light(ambient=ambient, diffuse=diffuse, specular=specular, position=position)

        #lets give the light a red hue
        light.diffuse = ( 1.0, 1.0, 1.0, 1.0 )

        #if the light leaf is added to the same group as the children it is going
        #to light, it would move, and rotate with its children.
        #this is not the effect we want in this case, so we add the light to its
        #own group, which we will call environment.
        self.environment = qgl.scene.Group()

        #Now we add the different nodes and leaves into a tree structure using the .add method. 
        self.root_node.add(self.viewport)
        self.root_node.add(self.menuViewport)
        self.viewport.add(self.environment)
        self.environment.add(light)
        self.environment.add(self.gameGroup)
        self.environment.translate = Point3( 0, -15, 0)
        self.environment.axis = Vector3(1,0,0)
        self.environment.angle = 30

        self.localBoard = RemoteBoard()
        self.createBoardGroup()

        self.menuGroup = Menu()
        self.menuViewport.add( self.menuGroup )
        #menuOptions = [
        #    ("Join new game", self.joinServer),
        #    ("Keep playing", self.keepPlaying),
        #    ("Exit game", self.exitGame),
        #]
        #self.menuGroup.setOptions(menuOptions)


        #Before the structure can be drawn, it needs to be compiled.
        #To do this, we ask the root node to accept the compiler visitor.
        #If any new nodes are added later in the program, they must also
        #accept the compiler visitor before they can be drawn.
        self.root_node.accept(self.compiler)
        self.pieces = {}
        self.onHand = None

    def createBoardGroup(self):
        self.boardGroup = qgl.scene.Group()
        boardY = -1.0
        self.boardGroup.translate = (0,boardY,0)
        #boardTexture = qgl.scene.state.Texture("art/board.jpg")
        #self.boardGroup.add(boardTexture)
        self.gameGroup.add(self.boardGroup)
        self.boardPlane = Plane( Point3(0,boardY,0), Point3(0,boardY,1), Point3(1,boardY,1) )
        self.pyramids = []

    def setupLoop(self):
        self.loopingCall = task.LoopingCall(self.loop)
        self.loopingCall.start(1.0/FPS)

    def buildBoard(self, side):
        # remove the previous board, if it was already there
        self.gameGroup.remove(self.boardGroup)
        self.gameGroup.remove(*self.pyramids)
        self.onHand = None
        self.pyramids = []
        self.createBoardGroup()

        hex = HexagonNode( 2.1 )
        #color = (0.2, 0.2, 0.2, 1)
        #darkcolor = (0.2, 0.2, 0.2, 1)
        ambient, diffuse, specular, shininess, emissive = (0.0, 0.0, 0.0, 1.0), (0.1, 0.35, 0.1, 1.0), (0.45, 0.55, 0.45, 1.0), (128.0*.25,), (0.1, 0.1, 0.1, 1.0)
        material = qgl.scene.state.Material(ambient=ambient, diffuse=diffuse, specular=specular, shininess=shininess, emissive=emissive )
        self.boardGroup.add( material )

        self.localBoard.side = side
        for x in range(side):
            for z in range(side):
                cell = qgl.scene.Group()
                cell.selectable = True
                cell.position = (x,z)
                self.boardGroup.add(cell)

                cell.translate = (x-side/2 + ((z%2)*0.5+0.25))*4, 0, (z+0.5-side/2)*3.5777087639996634
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
        #from subdivide import subdivideTriangles
        #pyramidTriangles = subdivideTriangles(pyramidTriangles)
        #pyramidTriangles = subdivideTriangles(pyramidTriangles)
        #pyramidTriangles = subdivideTriangles(pyramidTriangles)
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
            self.pyramids.append(pyramid)

        self.gameGroup.accept(self.compiler)

    def recompile(self, node):
        node.accept(self.compiler)

    def joinServer(self):
        self.start()
        pass

    def keepPlaying(self):
        self.menuDisable()

    def exitGame(self):
        reactor.stop()

    def connect(self):
        factory = pb.PBClientFactory() 
        print "connecting to server...",
        reactor.connectTCP("127.0.0.1", 9091, factory)
        d = factory.getRootObject().addCallback(self.gotServer)

    def gotServer(self, server):
        self.server = server
        print "getting games..."
        server.callRemote("games").addCallback(self.gotGames)

    def showFailure(self, *f):
        print f

    def gameJoiner(self, game):
        def f():
            self.menuDisable()
            self.server.game = game
            print "joining game..." + repr(game)
            game.callRemote("join", self.getPlayerName()).addCallbacks(self.gotPlayer, self.showFailure)
        return f

    def gotGames(self, games):
        self.server.game = games
        menuOptions = []
        for game in games:
            print dir(game)
            menuOptions.append( ("Join " + repr(game), self.gameJoiner(game) ) )
        menuOptions.append( ("Create new game", self.createGame) )
        self.menuGroup.setOptions(menuOptions)
        self.recompile(self.menuGroup)
        self.menuEnable()
        print games

    playerName = "alecu" + repr(random.random())
    def getPlayerName(self):
        return self.playerName

    def createGame(self):
        self.menuDisable()
        print "creating game..."
        self.server.callRemote("create_game", self.getPlayerName()).addCallback(self.gotGame)

    def gotGame(self, game):
        self.server.game = game
        #print "joining sample users..."
        #game.callRemote("sample_game", 4).addCallback(self.gotPlayer)
        game.callRemote("join", self.getPlayerName()).addCallbacks(self.gotPlayer, self.showFailure)

    def gotPlayer(self, player):
        self.server.player = player
        print "setting board..."
        self.server.player.callRemote("set_board", self.localBoard).addCallback(self.boardSet)

    def boardSet(self, *a):
        self.showReadyMenu()

    def showReadyMenu(self):
        menuOptions = []
        menuOptions.append( ("Ready to start", self.imReady) )
        self.menuGroup.setOptions(menuOptions)
        self.recompile(self.menuGroup)
        self.menuEnable()

    def imReady(self):
        print "letting the server know that the player is ready..."
        self.server.player.callRemote("set_ready").addCallback(self.playerReady)

    def playerReady(self, *a):
        print "getting other players' names..."
        self.server.game.callRemote("players").addCallback(self.gotPlayers)

    def gotPlayers(self, plys):
        self.players = plys
        print "getting board side..."
        self.getSide()

    def getSide(self):
        self.server.game.callRemote("get_side").addCallbacks(self.gotSide, self.cannotGetSide)

    def cannotGetSide(self, f):
        reactor.callLater(.5, self.getSide)

    def gotSide(self, side):
        print "building the board..."
        self.buildBoard(side)
        if SHUFFLE_THE_BOARD:
            print "shuffling the board..."
            self.server.game.callRemote("shuffle").addCallback(self.boardShuffled)
        else:
            self.boardShuffled()

    def boardShuffled(self, *a):
        pass
        #self.menuDisable()

    def toggleMenu(self):
        if self.menuEnabled:
            self.menuDisable()
        else:
            self.menuEnable()

    def menuEnable(self):
        self.menuViewport.enable()
        self.menuEnabled = True

    def menuDisable(self):
        self.menuViewport.disable()
        self.menuEnabled = False

    def handleMenuEvent(self, event):
        if event.type is MOUSEBUTTONDOWN:
            if event.button == 1:
                self.menuGroup.clicked()

    def handleBoardEvent(self, event):
        if event.type is MOUSEMOTION:
            if pygame.key.get_mods() & KMOD_CTRL:
                self.gameGroup.angle += event.rel[0]/2.5
        elif event.type is MOUSEBUTTONDOWN:
            if event.button == 1:
                #tell the picker we are interested in the area clicked by the mouse
                self.picker.set_position(event.pos)
                #ask the root node to accept the picker.
                self.root_node.accept(self.picker)
                #picker.hits will be a list of nodes which were rendered at the position.
                if len(self.picker.hits) > 0:
                    self.picked = self.picker.hits[0]
                    if self.picked is self.onHand:
                        if len(self.picker.hits) > 1:
                            self.picked = self.picker.hits[1]
                        else:
                            self.picked = None
                if self.picked is not None:
                    print "clickeada la pieza...", self.picked
                    if hasattr(self.picked, "id"):
                        if self.onHand is None:
                            def gotPiece(result, piece):
                                print "Fue levantada la pieza...", piece
                                self.onHand = piece
                            def noPiece(failure, *a):
                                print failure, failure.getErrorMessage(), failure.type, a
                                # failure.trap...

                            stack = self.localBoard.board[self.picked.position]
                            if len(stack) == 1:
                                d=self.server.player.callRemote("pick", self.picked.position)
                            else:
                                d=self.server.player.callRemote("mine", self.picked.position, self.picked.id)
                            d.addCallbacks(gotPiece, noPiece, [self.picked])

                        else:
                            def pieceCapped(result, *a):
                                print "capped!", result, a
                                self.onHand = None
                            def cannotCap(failure):
                                print "cannot cap!"
                            print "capping..."
                            d=self.server.player.callRemote("cap", self.picked.position)
                            d.addCallback(pieceCapped, cannotCap)
                    elif hasattr(self.picked, "position"):
                        def pieceDropped(result):
                            print "Soltada la pieza...", result
                            self.onHand = None
                        def cannotDrop(failure):
                            print "No se puede soltar la pieza...", failure
                        d=self.server.player.callRemote("drop", self.picked.position)
                        d.addCallbacks(pieceDropped, cannotDrop)
            elif event.button == 4:
                self.newPosition = event.pos
                self.gameGroup.angle -= 5
            elif event.button == 5:
                self.newPosition = event.pos
                self.gameGroup.angle += 5

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

                    piece.translate = (x-side/2 + ((z%2)*0.5+0.25))*4, -1+scale + y, (z+0.5-side/2)*3.5777087639996634
                    lastscale = scale

        self.newPosition = None
        if self.menuEnabled:
            self.gameGroup.angle += 2
            self.newPosition = pygame.mouse.get_pos()

        #process pygame events.
        for event in pygame.event.get():
            if event.type is MOUSEMOTION:
                self.newPosition = event.pos
            if event.type is QUIT:
                self.exitGame()
            elif event.type is KEYDOWN and event.key is K_q:
                self.exitGame()
            elif event.type is KEYDOWN and event.key is K_ESCAPE:
                self.toggleMenu()
            elif self.menuEnabled:
                self.handleMenuEvent(event)
            else:
                self.handleBoardEvent(event)

        if self.newPosition is not None and self.onHand is not None:
            projection = Matrix4.new_perspective(math.radians(45.0), self.viewport.aspect, 10.0, 10000.0)
            modelview = Matrix4.new_identity()
            modelview = modelview.translate(*self.environment.translate).rotate_axis(math.radians(self.environment.angle), self.environment.axis)
            modelview = modelview.translate(*self.gameGroup.translate).rotate_axis(math.radians(self.gameGroup.angle), self.gameGroup.axis)

            mx, my = self.newPosition
            ray = selection.generateSelectionRay( mx, WINDOW_SIZE[1]-my, self.viewport.screen_dimensions, modelview, projection )
            point = self.boardPlane.intersect(ray)
            if point is not None:
                x, y, z = point
                scale = self.onHand.scale[0]
                self.onHand.translate = x, scale-1, z
            #print "feel my death ray...", self.newPosition, ray, point

        if self.menuEnabled and self.newPosition is not None:
            if self.newPosition != self.lastMenuPosition:
                self.lastMenuPosition = self.newPosition
                # buscar cual item se esta apuntando
                self.environment.disable()
                self.picker.set_position(self.newPosition)
                self.root_node.accept(self.picker)
                self.environment.enable()
                if len(self.picker.hits) > 0:
                    picked = self.picker.hits[0]
                    self.menuGroup.selected(picked)
                else:
                    self.menuGroup.selected(None)

        #ask the root node to accept the render visitor.
        #This will draw the structure onto the screen.
        #notice that QGL draws everything from the centre, and
        #that the 0,0 point in a QGL screen is the center of the screen.
        self.root_node.accept(self.render)
        pygame.display.flip()


if __name__ == "__main__":
    game=Game()
    game.setupLoop()
    game.connect()
    reactor.run()
    pygame.quit()
