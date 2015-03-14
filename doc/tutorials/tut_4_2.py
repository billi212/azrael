import time
import numpy as np
import azrael.startup
import azrael.parts as parts
from azrael.util import Template, Fragment


def defineCube():
    """
    Return the vertices of a cubes with side length 1.

    Nothing interesting happens here.
    """
    vert = 0.5 * np.array([
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
    return vert


def createTemplate():
    # Create the vertices for a unit cube.
    vert = defineCube()

    # Define the one and only geometry fragment for this template.
    frags = [Fragment('frag_1', vert, [], [])]

    # Define the collision shape. This is still work in progress so just accept
    # the magic numbers for now.
    cs = [4, 1, 1, 1]

    # Define a booster
    myBooster = parts.Booster(
        partID=0,                         # Booster has this ID,
        pos=[0, 0, 0],                    # is located here,
        direction=[1, 0, 0],              # and points into this direction.
        minval=0,                         # Minimum allowed force.
        maxval=10.0,                      # Maximum allowed force.
        force=0                           # Initial force.
    )

    # Compile and return the template.
    return Template('my_first_template', cs, frags, [myBooster], [])


def main():
    # Start the Azrael stack.
    az = azrael.startup.AzraelStack()
    az.start()

    # Instantiate a Client to communicate with Azrael.
    client = azrael.client.Client()

    # Verify that the client is connected.
    ret = client.ping()
    assert ret.ok

    # Create the template and send it to Azrael.
    template = createTemplate()
    client.addTemplates([template])

    # Spawn two objects from the just added template. The only difference is
    # their (x, y, z) position in space.
    spawn_param = [
        {'position': [0, 0, 0],
         'template': template.name}
    ]
    ret = client.spawn(spawn_param)
    objID = ret.data[0]
    print('Spawned one object with objIDs={}'.format(objID))
    print('Point your browser to http://localhost:8080 to see them')

    # Wait until the user presses <ctrl-c>.
    try:
        while True:
            time.sleep(1)

            # Generate a new force value at random.
            force  = 0.01 * np.random.randn()

            # Assemble the command to the booster (the partID must match the
            # one we used to define the booster!)
            cmd = parts.CmdBooster(partID=0, force=force)

            # Send the command to Azrael.
            ret = client.controlParts(objID, [cmd], [])
            print(ret)
            print('New Force: {:.2f} Newton'.format(force))
    except KeyboardInterrupt:
        pass

    # Terminate the stack.
    az.stop()


if __name__ == '__main__':
    main()