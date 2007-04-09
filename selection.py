# taken from http://groups.google.com/group/pyglet-users/web/geoffrey-a-board-game-environment
# that's based on: http://nehe.gamedev.net/data/articles/article.asp?article=13

from OpenGL.GL import *
from OpenGL.GLU import *
from euclid import *

def generateSelectionRay(x, y):
    viewport = glGetIntegerv(GL_VIEWPORT) # Retrieves The Viewport Values (X, Y, Width, Height)
    modelview = glGetDoublev(GL_MODELVIEW_MATRIX) # Retrieve The Modelview Matrix
    projection = glGetDoublev(GL_PROJECTION_MATRIX) # Retrieve The Projection Matrix 

    def unProject(x, y, z, modelview, projection):
        result = gluUnProject(x, y, z, modelview, projection, viewport)
        return Point3(*result)

    return LineSegment3(
        unProject(x, y, 0., modelview, projection),
        unProject(x, y, 1., modelview, projection),
    )
