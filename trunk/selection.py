# taken from http://groups.google.com/group/pyglet-users/web/geoffrey-a-board-game-environment
# that's based on: http://nehe.gamedev.net/data/articles/article.asp?article=13

from OpenGL.GL import *
from OpenGL.GLU import *
from euclid import *

def generateSelectionRay(x, y, viewport, modelview, projection):
    def unProject(x, y, z, modelview, projection):
        result = gluUnProject(x, y, z, list(modelview), list(projection), viewport)
        return Point3(*result)

    return LineSegment3(
        unProject(x, y, 0., modelview, projection),
        unProject(x, y, 1., modelview, projection),
    )
