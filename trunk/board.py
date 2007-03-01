from __future__ import division
import pygame
import random
from pygame.locals import *

import qgl
from OpenGL.GL import *
from OpenGL.GLU import *
    
import model
import math

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
    flags =  OPENGL|DOUBLEBUF|HWSURFACE
    pygame.display.set_mode((800,600), flags)
    
    
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
    
    #leaves are added to the group. The texture leaf loads a texture image ready for drawing. Any sphere leaves, which are drawn 
    #after a texture leaf will be rendered with the texture image. Sphere has 1 argument, which is the sphere radius, and two keywords
    #which control how many segments are used to approximate the sphere.
    sphere = qgl.scene.state.Sphere(1, x_segments=16, y_segments=16)
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

    game = model.random_moved(4) # model.game_for(4)
    for player, color in zip(game.players, TOWERCOLOURS):
        player.color = color

    boardGroup = qgl.scene.Group()
    #boardGroup.axis = (1,0,0)
    #boardGroup.angle -= 90
    boardGroup.translate = (0,-1,0)
    #texture = qgl.scene.state.Texture("art/board.jpg")
    #boardGroup.add(texture)
    group.add(boardGroup)

    color = (0.2, 0.2, 0.2, 1)
    darkcolor = (0.2, 0.2, 0.2, 1)
    material = qgl.scene.state.Material(specular=color, emissive=darkcolor )
    boardGroup.add( material )

    for x in range(game.board.side):
        for z in range(game.board.side):
            square = qgl.scene.Group()
            square.selectable = True
            square.coordinates = (x,z)
            boardGroup.add(square)

            square.translate = (x-game.board.side/2 + ((z%2)*0.5+0.25))*4, 0, (z-game.board.side/2)*3.5777087639996634
            square.angle = 90
            square.axis= 0,1,0
            #quad = qgl.scene.state.Quad( (4, 3.5777087639996634) )
            hex = Hexagon( 2.1 )
            square.add( hex )

    for stack in game.board:
        for piece in stack.pieces:
            tower = qgl.scene.Group()
            tower.piece = piece
            tower.stack = stack
            tower.selectable = True
            piece.tower = tower

            scale = TOWERSCALES[piece.size-1]
            tower.scale = [scale]*3

            color = piece.player.color
            darkcolor = (color[0]*0.15, color[1]*0.15, color[2]*0.2, 1.0)
            material = qgl.scene.state.Material(specular=color, emissive=darkcolor )

            tower.add(material, tria)
            group.add(tower)

    #Before the structure can be drawn, it needs to be compiled. To do this, we ask the root node to accept the compiler visitor.
    #If any new nodes are added later in the program, they must also accept the compiler visitor before they can be drawn.
    root_node.accept(compiler)
    clock = pygame.time.Clock()

    piece = None
    #the main render loop
    lastPosition = None
    lastSelected = None
    while True:
        # place every piece in their own spot
        for stack in game.board:
            x, z = stack.position
            y = 0
            lastscale = 0
            for piece in stack.pieces:
                scale = TOWERSCALES[piece.size-1]

                if lastscale != 0:
                    y += 3*(lastscale - scale) + 0.4

                piece.tower.translate = (x-game.board.side/2 + ((z%2)*0.5+0.25))*4, -1+scale + y, (z-game.board.side/2)*3.5777087639996634
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
                pick = picker.hits[0]

        #process pygame events.
        for event in pygame.event.get():
            if event.type is QUIT:
                return
            elif event.type is KEYDOWN and event.key is K_ESCAPE:
                return
            elif event.type is MOUSEBUTTONDOWN:
                if len(picker.hits) > 0:
                    pick = picker.hits[0]
                    #pick.angle += 10
                    if hasattr(pick, "stack"):
                        if player.on_hand is None:
                            try:
                                piece = player.pick(pick.stack)
                                #pick.angle += 10
                                print pick, piece
                            except model.GameError, e:
                                print e
                                pass
                        else:
                            try:
                                player.cap(pick.stack)
                            except model.GameError, e:
                                print e
                                pass
                            
                    elif hasattr(pick, "coordinates"):
                        try:
                            player.drop(pick.coordinates)
                        except model.GameError, e:
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

