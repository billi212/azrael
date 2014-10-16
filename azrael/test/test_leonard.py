import sys
import time
import pytest
import IPython
import subprocess
import azrael.clerk
import azrael.clacks
import azrael.leonard
import azrael.controller
import azrael.bullet.btInterface as btInterface
import azrael.bullet.bullet_data as bullet_data

from azrael.util import int2id, id2int

import numpy as np

ipshell = IPython.embed


def killAzrael():
    subprocess.call(['pkill', 'killme'])


def startAzrael(ctrl_type):
    """
    Start all Azrael services and return their handles.

    ``ctrl_type`` may be  either 'ZeroMQ' or 'Websocket'. The only difference
    this makes is that the 'Websocket' version will also start a Clacks server,
    whereas for 'ZeroMQ' the respective handle will be **None**.

    :param str ctrl_type: the controller type ('ZeroMQ' or 'Websocket').
    :return: handles to (clerk, ctrl, clacks)
    """
    killAzrael()

    # Start Clerk and instantiate Controller.
    clerk = azrael.clerk.Clerk(reset=True)
    clerk.start()

    if ctrl_type == 'ZeroMQ':
        # Instantiate the ZeroMQ version of the Controller.
        ctrl = azrael.controller.ControllerBase()
        ctrl.setupZMQ()
        ctrl.connectToClerk()

        # Do not start a Clacks process.
        clacks = None
    elif ctrl_type == 'Websocket':
        # Start a Clacks process.
        clacks = azrael.clacks.ClacksServer()
        clacks.start()

        # Instantiate the Websocket version of the Controller.
        ctrl = azrael.wscontroller.WSControllerBase(
            'ws://127.0.0.1:8080/websocket', 1)
        assert ctrl.ping()
    else:
        print('Unknown controller type <{}>'.format(ctrl_type))
        assert False
    return clerk, ctrl, clacks


def stopAzrael(clerk, clacks):
    """
    Kill all processes related to Azrael.

    :param clerk: handle to Clerk process.
    :param clacks: handle to Clacks process.
    """
    # Terminate the Clerk.
    clerk.terminate()
    clerk.join(timeout=3)

    # Terminate Clacks (if one was started).
    if clacks is not None:
        clacks.terminate()
        clacks.join(timeout=3)

    # Forcefully terminate everything.
    killAzrael()


@pytest.mark.parametrize(
    'clsLeonard',
    [azrael.leonard.LeonardBase,
     azrael.leonard.LeonardBaseWorkpackages,
     azrael.leonard.LeonardBaseWPRMQ,
     azrael.leonard.LeonardBulletMonolithic,
     azrael.leonard.LeonardBulletSweeping])
def test_move_single_object(clsLeonard):
    """
    Create a single object with non-zero initial speed and ensure Leonard moves
    it accordingly.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael('ZeroMQ')

    # Instantiate Leonard.
    leonard = clsLeonard()
    leonard.setup()

    # Constants and parameters for this test.
    templateID = '_templateCube'.encode('utf8')

    # Create a cube (a cube always exists in Azrael's template database).
    ok, id_0 = ctrl.spawn(None, templateID, pos=[0, 0, 0], vel=[0, 0, 0])
    assert ok

    # Advance the simulation by 1s and verify that nothing moved.
    leonard.step(1.0, 60)
    ok, sv = btInterface.getStateVariables([id_0])
    assert ok
    np.array_equal(sv[0].position, [0, 0, 0])

    # Give the object a velocity.
    ok, sv = btInterface.getStateVariables([id_0])
    assert ok
    sv[0].velocityLin[:] = [1, 0, 0]
    assert btInterface.update(id_0, sv[0])

    # Advance the simulation by another second and verify the objects have
    # moved accordingly.
    leonard.step(1.0, 60)
    ok, sv = btInterface.getStateVariables([id_0])
    assert ok
    assert 0.9 <= sv[0].position[0] < 1.1
    assert sv[0].position[1] == sv[0].position[2] == 0

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize(
    'clsLeonard',
    [azrael.leonard.LeonardBase,
     azrael.leonard.LeonardBaseWorkpackages,
     azrael.leonard.LeonardBaseWPRMQ,
     azrael.leonard.LeonardBulletMonolithic,
     azrael.leonard.LeonardBulletSweeping])
def test_move_two_objects_no_collision(clsLeonard):
    """
    Same as previous test but with two objects.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael('ZeroMQ')

    # Instantiate Leonard.
    leonard = clsLeonard()
    leonard.setup()

    # Constants and parameters for this test.
    templateID = '_templateCube'.encode('utf8')

    # Create two cubic objects.
    ok, id_0 = ctrl.spawn(None, templateID, pos=[0, 0, 0], vel=[1, 0, 0])
    assert ok
    ok, id_1 = ctrl.spawn(None, templateID, pos=[0, 10, 0], vel=[0, -1, 0])
    assert ok

    # Advance the simulation by 1s and verify the objects moved accordingly.
    leonard.step(1.0, 60)
    ok, sv = btInterface.getStateVariables([id_0])
    assert ok
    pos_0 = sv[0].position

    ok, sv = btInterface.getStateVariables([id_1])
    assert ok
    pos_1 = sv[0].position

    assert pos_0[1] == pos_0[2] == 0
    assert pos_1[0] == pos_1[2] == 0
    assert 0.9 <= pos_0[0] <= 1.1
    assert 8.9 <= pos_1[1] <= 9.1

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


@pytest.mark.parametrize(
    'clsWorker',
    [azrael.leonard.LeonardRMQWorker,
     azrael.leonard.LeonardRMQWorkerBullet])
def test_multiple_workers(clsWorker):
    """
    Create several objects on parallel trajectories. Use multiple
    instances of LeonardWorkers.
    """
    # Start the necessary services.
    clerk, ctrl, clacks = startAzrael('ZeroMQ')

    # Constants and parameters for this test.
    templateID = '_templateCube'.encode('utf8')
    num_workers, num_objects = 10, 20
    assert num_objects >= num_workers

    # Instantiate Leonard.
    leonard = azrael.leonard.LeonardBaseWPRMQ(num_workers, clsWorker)
    leonard.setup()

    # Create several cubic objects.
    templateID = '_templateCube'.encode('utf8')
    list_ids = []
    for ii in range(num_objects):
        ok, cur_id = ctrl.spawn(
            None, templateID, pos=[0, 10 * ii, 0], vel=[1, 0, 0])
        assert ok
        list_ids.append(cur_id)
    del cur_id, ok

    # Advance the simulation by one second.
    leonard.step(1.0, 60)

    # All objects must have moved the same distance.
    for ii, cur_id in enumerate(list_ids):
        ok, sv = btInterface.getStateVariables([cur_id])
        assert ok
        cur_pos = sv[0].position
        assert 0.9 <= cur_pos[0] <= 1.1
        assert cur_pos[1] == 10 * ii
        assert cur_pos[2] == 0

    # All workers should have been utilised.
    assert len(leonard.used_workers) == num_workers

    # Shutdown the services.
    stopAzrael(clerk, clacks)
    print('Test passed')


def test_sweeping_2objects():
    """
    Ensure the Sweeping algorithm finds the correct sets.

    The algorithm takes a list of dictionarys and returns a list of lists.

    The input dictionary each contains the AABB coordinates. The output list
    contains the set of overlapping AABBs.
    """
    # Convenience variables.
    sweeping = azrael.leonard.sweeping
    labels = np.arange(2)

    # Two orthogonal objects.
    aabbs = [{'x': [4, 5], 'y': [3.5, 4], 'z': [5, 6.5]},
             {'x': [1, 2], 'y': [3.5, 4], 'z': [5, 6.5]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([1]), set([0])])

    # Repeat the test but use a different set of labels.
    res = sweeping(aabbs, np.array([3, 10], np.int64), 'x')
    assert sorted(res) == sorted([set([10]), set([3])])

    # One object inside the other.
    aabbs = [{'x': [2, 4], 'y': [3.5, 4], 'z': [5, 6.5]},
             {'x': [1, 5], 'y': [3.5, 4], 'z': [5, 6.5]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([1, 0])])

    # Partially overlapping to the right of the first object.
    aabbs = [{'x': [1, 5], 'y': [3.5, 4], 'z': [5, 6.5]},
             {'x': [2, 4], 'y': [3.5, 4], 'z': [5, 6.5]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([1, 0])])

    # Partially overlapping to the left of the first object.
    aabbs = [{'x': [1, 5], 'y': [3.5, 4], 'z': [5, 6.5]},
             {'x': [2, 4], 'y': [3.5, 4], 'z': [5, 6.5]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([1, 0])])

    # Test Sweeping in the 'y' and 'z' dimension as well.
    aabbs = [{'x': [1, 5], 'y': [1, 5], 'z': [1, 5]},
             {'x': [2, 4], 'y': [2, 4], 'z': [2, 4]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    assert sweeping(aabbs, labels, 'x') == sweeping(aabbs, labels, 'y')
    assert sweeping(aabbs, labels, 'x') == sweeping(aabbs, labels, 'z')

    # Pass no object to the Sweeping algorithm.
    assert sweeping([], np.array([], np.int64), 'x') == []

    # Pass only a single object to the Sweeping algorithm.
    aabbs = [{'x': [1, 5], 'y': [3.5, 4], 'z': [5, 6.5]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, np.array([0], np.int64), 'x')
    assert sorted(res) == sorted([set([0])])

    print('Test passed')


def test_sweeping_3objects():
    """
    Same as test_sweeping_2objects but with three objects.
    """
    # Convenience variable.
    sweeping = azrael.leonard.sweeping
    labels = np.arange(3)

    # Three non-overlapping objects.
    aabbs = [{'x': [1, 2]}, {'x': [3, 4]}, {'x': [5, 6]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([0]), set([1]), set([2])])

    # First and second overlap.
    aabbs = [{'x': [1, 2]}, {'x': [1.5, 4]}, {'x': [5, 6]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([0, 1]), set([2])])

    # Repeat test with different labels.
    res = sweeping(aabbs, np.array([2, 4, 10], np.int64), 'x')
    assert sorted(res) == sorted([set([2, 4]), set([10])])

    # First overlaps with second, second overlaps with third, but third does
    # not overlap with first. The algorithm must nevertheless return all three
    # in a single set.
    aabbs = [{'x': [1, 2]}, {'x': [1.5, 4]}, {'x': [3, 6]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([0, 1, 2])])

    # First and third overlap.
    aabbs = [{'x': [1, 2]}, {'x': [10, 11]}, {'x': [0, 1.5]}]
    aabbs = [{'aabb': _} for _ in aabbs]
    res = sweeping(aabbs, labels, 'x')
    assert sorted(res) == sorted([set([0, 2]), set([1])])

    print('Test passed')


@pytest.mark.parametrize('dim', [0, 1, 2])
def test_computeCollisionSetsAABB(dim):
    """
    Create a sequence of 10 test objects. Their position only differs in the
    ``dim`` dimension.

    Then use subsets of these 10 objects to test basic collision detection.
    """
    # Reset the SV database.
    btInterface.initSVDB(reset=True)

    # Create several objects for this test.
    all_id = [int2id(_) for _ in range(10)]

    if dim == 0:
        SVs = [bullet_data.BulletData(position=[_, 0, 0]) for _ in range(10)]
    elif dim == 1:
        SVs = [bullet_data.BulletData(position=[0, _, 0]) for _ in range(10)]
    elif dim == 2:
        SVs = [bullet_data.BulletData(position=[0, 0, _]) for _ in range(10)]
    else:
        print('Invalid dimension for this test')
        assert False

    # Add all objects to the SV DB.
    for objID, sv in zip(all_id, SVs):
        assert btInterface.spawn(objID, sv, np.int64(1).tostring(), 1.0)

    # Retrieve all SVs as Leonard does.
    ok, all_sv = btInterface.getStateVariables(all_id)
    assert (ok, len(all_id)) == (True, len(all_sv))

    # Delete auxiliaray variables.
    del SVs

    def ccsWrapper(IDs_hr, expected_hr):
        """
        Assert that the ``IDs_hr`` were split into the ``expected_hr`` lists.

        This is merely a convenience wrapper to facilitate readable tests.

        This wrapper converts the human readable entries in ``IDs_hr``  into
        the internally used binary format. It then passes this new list, along
        with the corresponding SVs to the collision detection algorithm.
        Finally, it converts the returned list of object sets back into human
        readable list of object sets and compares them for equality.
        """
        # Compile the set of SVs for curIDs.
        sv = [all_sv[_] for _ in IDs_hr]

        # Convert the human readable IDs to the binary format.
        test_objIDs = [int2id(_) for _ in IDs_hr]

        # Determine the list of potential collision sets.
        ok, res = azrael.leonard.computeCollisionSetsAABB(test_objIDs, sv)
        assert ok

        # Convert the IDs in res back to human readable format.
        res_hr = [[id2int(_) for _ in __] for __ in res]

        # Convert the reference data to a sorted list of sets.
        expected_hr = sorted([set(_) for _ in expected_hr])
        res_hr = sorted([set(_) for _ in res_hr])

        # Return the equality of the two list of lists.
        assert expected_hr == res_hr

    # Two non-overlapping objects.
    ccsWrapper([0, 9], [[0], [9]])

    # Two overlapping objects.
    ccsWrapper([0, 1], [[0, 1]])

    # Three sets.
    ccsWrapper([0, 1, 5, 8, 9], [[0, 1], [5], [8, 9]])

    # Same test, but objects are passed in a different sequence. This must not
    # alter the test outcome.
    ccsWrapper([0, 5, 1, 9, 8], [[0, 1], [5], [8, 9]])

    # All objects must form one connected set.
    ccsWrapper(list(range(10)), [list(range(10))])

    print('Test passed')


if __name__ == '__main__':
    test_computeCollisionSetsAABB(0)
    test_sweeping_2objects()
    test_sweeping_3objects()
    test_multiple_workers(azrael.leonard.LeonardRMQWorker)
    test_multiple_workers(azrael.leonard.LeonardRMQWorkerBullet)
    test_move_single_object(azrael.leonard.LeonardBaseWPRMQ)
    test_move_two_objects_no_collision(azrael.leonard.LeonardBaseWPRMQ)
    test_move_single_object(azrael.leonard.LeonardBaseWorkpackages)
    test_move_two_objects_no_collision(azrael.leonard.LeonardBaseWorkpackages)
    test_move_single_object(azrael.leonard.LeonardBulletMonolithic)
    test_move_two_objects_no_collision(azrael.leonard.LeonardBulletMonolithic)
    test_move_single_object(azrael.leonard.LeonardBase)
    test_move_two_objects_no_collision(azrael.leonard.LeonardBase)
