# Copyright 2015, Oliver Nagy <olitheolix@gmail.com>
#
# This file is part of Azrael (https://github.com/olitheolix/azrael)
#
# Azrael is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Azrael is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Azrael. If not, see <http://www.gnu.org/licenses/>.
import os
import sys
import time
import subprocess
import numpy as np

# Import the necessary Azrael modules.
p = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(p, '..'))
sys.path.insert(0, os.path.join(p, '../viewer'))
del p

import model_import
import azrael.util as util
import azrael.aztypes as aztypes
from IPython import embed as ipshell
from azrael.aztypes import Template, FragMeta, FragRaw
from azrael.aztypes import CollShapeMeta, CollShapeEmpty, CollShapeSphere
from azrael.aztypes import CollShapeBox


def getRigidBody(scale: (int, float)=1,
                 imass: (int, float)=1,
                 restitution: (int, float)=0.9,
                 rotation: (tuple, list)=(0, 0, 0, 1),
                 position: (tuple, list, np.ndarray)=(0, 0, 0),
                 velocityLin: (tuple, list, np.ndarray)=(0, 0, 0),
                 velocityRot: (tuple, list, np.ndarray)=(0, 0, 0),
                 cshapes: dict=None,
                 axesLockLin: (tuple, list, np.ndarray)=(1, 1, 1),
                 axesLockRot: (tuple, list, np.ndarray)=(1, 1, 1),
                 version: int=0):
    if cshapes is None:
        cshapes = CollShapeMeta(cstype='Sphere',
                                position=(0, 0, 0),
                                rotation=(0, 0, 0, 1),
                                csdata=CollShapeSphere(radius=1))
        cshapes = {'Sphere': cshapes}
    return aztypes.RigidBodyData(scale, imass, restitution, rotation,
                                      position, velocityLin, velocityRot,
                                      cshapes, axesLockLin, axesLockRot,
                                      version)


def loadBoosterCubeBlender():
    """
    Load the Spaceship (if you want to call it that) from "boostercube.dae".

    This function is custom made for the Blender model of the cube with
    boosters because the model file is broken (no idea if the fault is with me,
    Blender, or the AssImp library).

    In particular, the ``loadModel`` function will only return the vertices for
    the body (cube) and *one* thruster (instead of six). To remedy, this
    function will attach a copy of that thruster to each side of the cube.  It
    will manually assign the colors too.
    """

    # Load the Collada model.
    p = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(p, 'boostercube.dae')
    vert, uv, rgb = loadModel(fname)

    # Extract the body and thruster component.
    body, thruster_z = np.array(vert[0]), np.array(vert[1])

    # The body should be a unit cube, but I do not know what Blender created
    # exactly. Therefore, determine the average position values (which should
    # all have the same value except for the sign).
    body_scale = np.mean(np.abs(body))

    # Reduce the thruster size, translate it to the cube's surface, and
    # duplicate on -z axis.
    thruster_z = 0.3 * np.reshape(thruster_z, (len(thruster_z) // 3, 3))
    thruster_z += [0, 0, -.6]
    thruster_z = thruster_z.flatten()
    thruster_z = np.hstack((thruster_z, -thruster_z))

    # Reshape the vertices into an N x 3 matrix and duplicate for the other
    # four thrusters.
    thruster_z = np.reshape(thruster_z, (len(thruster_z) // 3, 3))
    thruster_x, thruster_y = np.array(thruster_z), np.array(thruster_z)

    # We will compute the thrusters for the remaining two cube faces with a
    # 90degree rotation around the x- and y axis.
    s2 = 1 / np.sqrt(2)
    quat_x = util.Quaternion(s2, [s2, 0, 0])
    quat_y = util.Quaternion(s2, [0, s2, 0])
    for ii, (tx, ty) in enumerate(zip(thruster_x, thruster_y)):
        thruster_x[ii] = quat_x * tx
        thruster_y[ii] = quat_y * ty

    # Flatten the arrays.
    thruster_z = thruster_z.flatten()
    thruster_x = thruster_x.flatten()
    thruster_y = thruster_y.flatten()

    # Combine all thrusters and the body into a single triangle mesh. Then
    # scale the entire mesh to ensure the cube part is indeed a unit cube.
    vert = np.hstack((thruster_z, thruster_x, thruster_y, body))
    vert /= body_scale

    # Assign the same base color to all three thrusters.
    rgb_thruster = np.tile([0.8, 0, 0], len(thruster_x) // 3)
    rgb_thrusters = np.tile(rgb_thruster, 3)

    # Assign a color to the body.
    rgb_body = np.tile([0.8, 0.8, 0.8], len(body) // 3)

    # Combine the RGB vectors into single one to match the vector of vertices.
    rgb = np.hstack((rgb_thrusters, rgb_body))
    del rgb_thruster, rgb_thrusters, rgb_body

    # Add some random "noise" to the colors.
    rgb += 0.2 * (np.random.rand(len(rgb)) - 0.5)

    # Convert the RGB values from a triple of [0, 1] floats to a triple of [0,
    # 255] integers.
    rgb = rgb.clip(0, 1)
    rgb = np.array(rgb * 255, np.uint8)

    # Return the model data.
    return vert, uv, rgb


def loadModel(fname):
    """
    Load 3D model from ``fname`` and return the vertices, UV, and RGB arrays.
    """
    # Load the model.
    print('  Importing <{}>... '.format(fname), end='', flush=True)
    mesh = model_import.loadModelAll(fname)

    # The model may contain several sub-models. Each one has a set of vertices,
    # UV- and texture maps. The following code simply flattens the three lists
    # of lists into just three lists.
    vert = np.array(mesh['vertices']).flatten()
    uv = np.array(mesh['UV']).flatten()
    rgb = np.array(mesh['RGB']).flatten()
    print('done')

    return vert, uv, rgb

def cubeGeometry(hlen_x=1.0, hlen_y=1.0, hlen_z=1.0):
    """
    Return the vertices and collision shape for a Box.

    The parameters ``hlen_*`` are the half lengths of the box in the respective
    dimension.
    """
    # Vertices that define a Cube.
    vert = 1 * np.array([
        -1.0, -1.0, -1.0,   -1.0, -1.0, +1.0,   -1.0, +1.0, +1.0,
        -1.0, -1.0, -1.0,   -1.0, +1.0, +1.0,   -1.0, +1.0, -1.0,
        +1.0, -1.0, -1.0,   +1.0, +1.0, +1.0,   +1.0, -1.0, +1.0,
        +1.0, -1.0, -1.0,   +1.0, +1.0, -1.0,   +1.0, +1.0, +1.0,
        +1.0, -1.0, +1.0,   -1.0, -1.0, -1.0,   +1.0, -1.0, -1.0,
        +1.0, -1.0, +1.0,   -1.0, -1.0, +1.0,   -1.0, -1.0, -1.0,
        +1.0, +1.0, +1.0,   +1.0, +1.0, -1.0,   -1.0, +1.0, -1.0,
        +1.0, +1.0, +1.0,   -1.0, +1.0, -1.0,   -1.0, +1.0, +1.0,
        +1.0, +1.0, -1.0,   -1.0, -1.0, -1.0,   -1.0, +1.0, -1.0,
        +1.0, +1.0, -1.0,   +1.0, -1.0, -1.0,   -1.0, -1.0, -1.0,
        -1.0, +1.0, +1.0,   -1.0, -1.0, +1.0,   +1.0, -1.0, +1.0,
        +1.0, +1.0, +1.0,   -1.0, +1.0, +1.0,   +1.0, -1.0, +1.0
    ])

    # Scale the x/y/z dimensions.
    vert[0::3] *= hlen_x
    vert[1::3] *= hlen_y
    vert[2::3] *= hlen_z

    # Convenience.
    box = CollShapeBox(hlen_x, hlen_y, hlen_z)
    cs = CollShapeMeta('box', (0, 0, 0), (0, 0, 0, 1), box)
    return vert, cs


def launchQtViewer(param):
    """
    Launch the Qt Viewer in a separate process.

    This function does not return until the viewer process finishes.
    """
    this_dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(this_dir, 'viewer.py')

    try:
        if param.noviewer:
            time.sleep(3600000000)
        else:
            subprocess.call(['python3', fname])
    except KeyboardInterrupt:
        pass