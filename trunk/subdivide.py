from __future__ import division
from euclid import *

def subdivideTriangle( points ):
    p1,p2,p3 = [ Point3(*p) for p in points ]
    p12 = (p2+p1)/2
    p23 = (p3+p2)/2
    p31 = (p1+p3)/2
    return [(p1,p12,p31), (p2,p23,p12), (p3, p31, p23), (p12,p23,p31) ]

def subdivideTriangles( triangleList ):
    ret = []
    for triangle in triangleList:
        ret.extend( subdivideTriangle(triangle) )
    return ret

if __name__ == "__main__":
    pyramidTriangles = [
        [(0,2,0), (-1,-1,-1), (1,-1,-1)],
        [(0,2,0), (1,-1,-1), (1,-1,1)],
        [(0,2,0), (1,-1,1), (-1,-1,1)],
        [(0,2,0), (-1,-1,1), (-1,-1,-1)],
    ]
    #print subdivideTriangle( pyramidTriangles[0] )
    print subdivideTriangles( pyramidTriangles )
