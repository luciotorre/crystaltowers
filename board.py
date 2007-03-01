from __future__ import division
import pygame
import random
from pygame.locals import *

import qgl
    
import model
TOWERCOLOURS = [
    (1.0, 0.0, 0.0, 1.0),
    (0.0, 0.8, 0.0, 1.0),
    (0.3, 0.3, 1.0, 1.0),
    (1.0, 1.0, 0.0, 1.0),
    (0.3, 0.8, 0.5, 1.0),
    #(0.8, 0.3, 1.0, 1.0),
]
TOWERSCALES = [ 0.5, 0.7, 1 ]


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
    quad = qgl.scene.state.Quad( (4*game.board.side, 4*game.board.side) )
    boardGroup.axis = (1,0,0)
    boardGroup.angle -= 90
    boardGroup.translate = (0,-1,0)
    texture = qgl.scene.state.Texture("art/board.jpg")
    boardGroup.add(texture)
    boardGroup.add(quad)
    group.add(boardGroup)

    for stack in game.board:
        x, z = stack.position

        for y, piece in enumerate(stack.pieces):
            tower = qgl.scene.Group()

            color = piece.player.color
            darkcolor = (color[0]*0.15, color[1]*0.15, color[2]*0.2, 1.0)
            material = qgl.scene.state.Material(specular=color, emissive=darkcolor )

            scale = TOWERSCALES[piece.size-1]
            tower.scale = [scale]*3
            tower.translate = (x-game.board.side/2 + ((z%2)*0.5+0.25))*4, -1+scale + y*.5, (z-game.board.side/2)*3.5777087639996634
            tower.add(material, tria)
            group.add(tower)

    #Before the structure can be drawn, it needs to be compiled. To do this, we ask the root node to accept the compiler visitor.
    #If any new nodes are added later in the program, they must also accept the compiler visitor before they can be drawn.
    root_node.accept(compiler)
    clock = pygame.time.Clock()
    #the main render loop
    while True:
        #process pygame events.
        for event in pygame.event.get():
            if event.type is QUIT:
                return
            elif event.type is KEYDOWN:
                return
        
        #the group node has attributes that can be changed to manipulate the position of its children.
        #if we change the groups axis attribute to (0,1,0), it will rotate on its vertical axis, which is what a planet would probably do.
        group.axis = (0,1,0)
        group.angle += 1
        #ask the root node to accept the render visitor. This will draw the structure onto the screen.
        #notice that QGL draws everything from the centre, and that the 0,0 point in a QGL screen is the center of the screen.
        root_node.accept(render)
        
        clock.tick(30)
        #flip the display
        pygame.display.flip()


main()

