from __future__ import division
import pygame
from pygame.locals import *

import qgl
from OpenGL.GL import *
from OpenGL.GLU import *
    
import math 
from euclid import *
import selection

class Scene:
    # hide the previous scenes in the SceneManager stack
    opaque = False

    def __init__(self):
        pass

    def exit(self, nextScene=None):
        self.manager.pop()
        if nextScene is not None:
            self.manager.push(nextScene)

    def paint(self):
        print "painting", id(self), 
        pass

    def pick(self):
        pass

    def handle(self, event):
        """if you want the event to be handled by the previous scene in the stack, then return it"""
        return event

    def step(self, deltaT):
        pass

class SceneManager:
    def __init__(self):
        """this is a stack of scenes"""
        self._scenes = []
        self.visibleScenes=[]

    def init(self, windowSize, framerate=30):
        pygame.init()
        flags =  OPENGL|DOUBLEBUF|HWSURFACE
        pygame.display.set_mode(windowSize, flags)
        self.framerate=framerate

    def buildVisibleScenes(self):
        self.visibleScenes=[]
        for scene in reversed(self._scenes):
            self.visibleScenes.insert(0, scene)
            if scene.opaque:
                break

    def step(self, deltaT):
        for event in pygame.event.get():
            for scene in reversed(self.visibleScenes):
                event = scene.handle(event)
                if event is None:
                    break

        for scene in self.visibleScenes:
            scene.step(deltaT)

    def paint(self):
        for scene in self.visibleScenes:
            scene.paint()

    def running(self):
        return len(self._scenes) > 0

    def run(self):
        clock = pygame.time.Clock()
        while self.running():
            deltaT = clock.tick(self.framerate)
            self.step(deltaT)
            self.paint()
            print "-"*80, deltaT

    def push(self, scene):
        self._scenes.append(scene)
        scene.manager=self
        self.buildVisibleScenes()

    def pop(self):
        scene=self._scenes.pop()
        scene.manager = None
        self.buildVisibleScenes()


class QGLSceneManager(SceneManager):
    def paint(self):
        SceneManager.paint(self)

manager = QGLSceneManager()

class TextScene(Scene):
    def __init__(self, label):
        Scene.__init__(self)
        self.label = label

    def paint(self):
        print "painting", id(self), self.label

    def handle(self, event):
        print "handling", id(self), self.label
        if event.type == KEYDOWN and event.key == K_ESCAPE:
            self.exit()
            return
        return event

    def step(self, deltaT):
        print "stepping", id(self), self.label

def __test__():
    manager.init( (640,480) )
    manager.push(TextScene("one"))
    t=TextScene("two")
    t.opaque=True
    manager.push(t)
    manager.push(TextScene("three"))
    manager.run()

if __name__ == "__main__":
    __test__()
