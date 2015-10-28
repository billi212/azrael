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

"""
Test the Clerk module.
"""
import zmq
import json
import time
import base64
import requests

import numpy as np
import unittest.mock as mock

import azrael.web
import azrael.clerk
import azrael.dibbler
import azrael.aztypes as aztypes
import azrael.config as config

from IPython import embed as ipshell
from azrael.aztypes import RetVal, CollShapeMeta
from azrael.aztypes import FragRaw
from azrael.test.test import getLeonard, killAzrael, getP2P, get6DofSpring2
from azrael.test.test import getFragRaw, getFragDae, getFragNone, getRigidBody
from azrael.test.test import getCSEmpty, getCSBox, getCSSphere
from azrael.test.test import getCSPlane, getTemplate


class TestClerk:
    @classmethod
    def setup_class(cls):
        killAzrael()
        cls.clerk = azrael.clerk.Clerk()

    @classmethod
    def teardown_class(cls):
        killAzrael()

    def setup_method(self, method):
        self.dibbler = azrael.dibbler.Dibbler()
        self.dibbler.reset()
        azrael.database.init()

        # Insert default objects. None of them has an actual geometry but
        # their collision shapes are: none, sphere, box.
        frag = {'NoName': getFragRaw()}
        rbs_empty = getRigidBody(cshapes={'csempty': getCSEmpty()})
        rbs_sphere = getRigidBody(cshapes={'cssphere': getCSSphere()})
        rbs_box = getRigidBody(cshapes={'csbox': getCSBox()})
        rbs_plane = getRigidBody(cshapes={'csplane': getCSPlane()})
        t1 = getTemplate('_templateEmpty', rbs=rbs_empty, fragments=frag)
        t2 = getTemplate('_templateSphere', rbs=rbs_sphere, fragments=frag)
        t3 = getTemplate('_templateBox', rbs=rbs_box, fragments=frag)
        t4 = getTemplate('_templatePlane', rbs=rbs_plane, fragments=frag)
        ret = self.clerk.addTemplates([t1, t2, t3, t4])
        assert ret.ok

    def teardown_method(self, method):
        self.dibbler.reset()
        azrael.database.init()

    def test_get_default_templates(self):
        """
        Query the default templates in Azrael.
        """
        # Instantiate a Clerk.
        clerk = self.clerk

        # Request an invalid ID.
        assert not clerk.getTemplates(['blah']).ok

        # Clerk has a few default objects. This one has no collision shape,...
        name_1 = '_templateEmpty'
        ret = clerk.getTemplates([name_1])
        assert ret.ok and (len(ret.data) == 1) and (name_1 in ret.data)
        assert ret.data[name_1]['template'].rbs.cshapes == {'csempty': getCSEmpty()}

        # ... this one is a sphere,...
        name_2 = '_templateSphere'
        ret = clerk.getTemplates([name_2])
        assert ret.ok and (len(ret.data) == 1) and (name_2 in ret.data)
        assert ret.data[name_2]['template'].rbs.cshapes == {'cssphere': getCSSphere()}

        # ... this one is a box,...
        name_3 = '_templateBox'
        ret = clerk.getTemplates([name_3])
        assert ret.ok and (len(ret.data) == 1) and (name_3 in ret.data)
        assert ret.data[name_3]['template'].rbs.cshapes == {'csbox': getCSBox()}

        # ... and this one is a static plane.
        name_4 = '_templatePlane'
        ret = clerk.getTemplates([name_4])
        assert ret.ok and (len(ret.data) == 1) and (name_4 in ret.data)
        assert ret.data[name_4]['template'].rbs.cshapes == {'csplane': getCSPlane()}

        # Retrieve all three again but with a single call.
        ret = clerk.getTemplates([name_1, name_2, name_3, name_4])
        assert ret.ok
        assert set(ret.data.keys()) == set((name_1, name_2, name_3, name_4))

        d = ret.data
        assert d[name_1]['template'].rbs.cshapes == {'csempty': getCSEmpty()}
        assert d[name_2]['template'].rbs.cshapes == {'cssphere': getCSSphere()}
        assert d[name_3]['template'].rbs.cshapes == {'csbox': getCSBox()}
        assert d[name_4]['template'].rbs.cshapes == {'csplane': getCSPlane()}

    def test_add_get_template_single(self):
        """
        Add a new object to the templateID DB and query it again.
        """
        # Convenience.
        clerk = azrael.clerk.Clerk()

        # Install a mock for Dibbler with an 'addTemplate' function that
        # always succeeds.
        mock_dibbler = mock.create_autospec(azrael.dibbler.Dibbler)
        clerk.dibbler = mock_dibbler

        # The mock must not have been called so far.
        assert mock_dibbler.addTemplate.call_count == 0

        # Convenience.
        body = getRigidBody(cshapes={'cssphere': getCSSphere()})

        # Request an invalid ID.
        assert not clerk.getTemplates(['blah']).ok

        # Wrong argument .
        ret = clerk.addTemplates([1])
        assert (ret.ok, ret.msg) == (False, 'Invalid template data')
        assert mock_dibbler.addTemplate.call_count == 0

        # Compile a template structure.
        frags = {'foo': getFragRaw()}
        temp = getTemplate('bar', rbs=body, fragments=frags)

        # Add template when 'saveModel' fails.
        mock_ret = RetVal(False, 't_error', {'url_frag': 'http://'})
        mock_dibbler.addTemplate.return_value = mock_ret
        ret = clerk.addTemplates([temp])
        assert (ret.ok, ret.msg) == (False, 't_error')
        assert mock_dibbler.addTemplate.call_count == 1

        # Add template when 'saveModel' succeeds.
        mock_ret = RetVal(True, None, {'url_frag': 'http://'})
        mock_dibbler.addTemplate.return_value = mock_ret
        assert clerk.addTemplates([temp]).ok
        assert mock_dibbler.addTemplate.call_count == 2

        # Adding the same template again must fail.
        assert not clerk.addTemplates([temp]).ok
        assert mock_dibbler.addTemplate.call_count == 3

        # Define a new object with two boosters and one factory unit.
        # The 'boosters' and 'factories' arguments are a list of named
        # tuples. Their first argument is the unit ID (Azrael does not
        # automatically assign any IDs).
        boosters = {
            '0': aztypes.Booster(pos=(0, 1, 2), direction=(0, 0, 1),
                               minval=0, maxval=0.5, force=0),
            '1': aztypes.Booster(pos=(6, 7, 8), direction=(0, 1, 0),
                               minval=1, maxval=1.5, force=0)
        }
        factories = {
            '0': aztypes.Factory(pos=(0, 0, 0), direction=(0, 0, 1),
                               templateID='_templateBox',
                               exit_speed=(0.1, 0.5))
        }

        # Add the new template.
        temp = getTemplate('t3',
                           rbs=body,
                           fragments=frags,
                           boosters=boosters,
                           factories=factories)
        assert clerk.addTemplates([temp]).ok
        assert mock_dibbler.addTemplate.call_count == 4

        # Retrieve the just created object and verify the collision shape,
        # factories, and boosters. Note: we cannot compare against `temp`
        # directly because the returned template does not contain the fragment
        # geometries; they have to be fetche separately via
        # clerk.getFragments, which is tested elsewhere.
        ret = clerk.getTemplates([temp.aid])
        assert ret.ok
        assert ret.data[temp.aid]['template'].rbs == body
        assert ret.data[temp.aid]['template'].boosters == temp.boosters
        assert ret.data[temp.aid]['template'].factories == temp.factories

        # Request the same templates multiple times in a single call. This must
        # return a dictionary with as many keys as there are unique template
        # IDs.
        ret = clerk.getTemplates([temp.aid, temp.aid, temp.aid])
        assert ret.ok and (len(ret.data) == 1) and (temp.aid in ret.data)

    def test_add_get_template_multi_url_mock(self):
        """
        Add- and fetch templates in bulk. This test mocks the Dibbler instance
        in Clerk to verify it is called correctly.
        """
        # Convenience.
        clerk = azrael.clerk.Clerk()

        # Install a mock for Dibbler with an 'addTemplate' function that
        # always succeeds.
        mock_dibbler = mock.create_autospec(azrael.dibbler.Dibbler)
        mock_ret = RetVal(True, None, {'url_frag': 'http://'})
        mock_dibbler.addTemplate.return_value = mock_ret
        clerk.dibbler = mock_dibbler

        # The mock must not have been called so far.
        assert mock_dibbler.addTemplate.call_count == 0

        # Convenience.
        name_1, name_2 = 't1', 't2'

        # Define two valid templates.
        frag_1 = {'foo': getFragRaw()}
        frag_2 = {'bar': getFragRaw()}
        t1 = getTemplate(name_1, fragments=frag_1)
        t2 = getTemplate(name_2, fragments=frag_2)

        # Uploading the templates must succeed.
        assert clerk.addTemplates([t1, t2]).ok
        assert mock_dibbler.addTemplate.call_count == 2

        # Attempt to upload the same templates again. This must fail.
        assert not clerk.addTemplates([t1, t2]).ok
        assert mock_dibbler.addTemplate.call_count == 4

        # Fetch the first template.
        ret = clerk.getTemplates([name_1])
        assert ret.ok
        assert list(ret.data[name_1]['template'].fragments.keys()) == ['foo']

        # Fetch the second template.
        ret = clerk.getTemplates([name_2])
        assert ret.ok
        assert list(ret.data[name_2]['template'].fragments.keys()) == ['bar']

        # Fetch both templates at once.
        ret = clerk.getTemplates([name_1, name_2])
        assert ret.ok and (len(ret.data) == 2)
        assert list(ret.data[name_1]['template'].fragments.keys()) == ['foo']
        assert list(ret.data[name_2]['template'].fragments.keys()) == ['bar']

    def test_add_get_template_multi_url(self):
        """
        Same as previous tests, but this time Dibbler is not mocked. This will
        make the templates available via an URL and this test verifies that
        they are correct.
        """
        # Convenience.
        clerk = self.clerk

        # Convenience.
        name_1, name_2 = 't1', 't2'

        # Define two valid templates.
        frag_1 = getFragRaw()
        frag_2 = getFragRaw()
        t1 = getTemplate(name_1, fragments={'foo': frag_1})
        t2 = getTemplate(name_2, fragments={'bar': frag_2})

        # Uploading the templates must succeed.
        assert clerk.addTemplates([t1, t2]).ok

        # Attempt to upload the same templates again. This must fail.
        assert not clerk.addTemplates([t1, t2]).ok

        # Fetch the just added template in order to get the URL where its
        # geometries are stored.
        ret = clerk.getTemplates([name_1])
        assert ret.ok
        frag_ret = ret.data[name_1]['template'].fragments['foo']

        url_template = config.url_templates
        assert frag_ret.fragtype == frag_1.fragtype
        assert ret.data[name_1]['url_frag'] == '{}/'.format(url_template) + name_1
        del ret, frag_ret

        # Fetch the second template.
        ret = clerk.getTemplates([name_2])
        assert ret.ok
        frag_ret = ret.data[name_2]['template'].fragments['bar']

        assert frag_ret.fragtype == frag_2.fragtype
        assert ret.data[name_2]['url_frag'] == config.url_templates + '/' + name_2
        del ret, frag_ret

        # Fetch both templates at once.
        ret = clerk.getTemplates([name_1, name_2])
        assert ret.ok and (len(ret.data) == 2)
        assert ret.data[name_1]['url_frag'] == '{}/'.format(url_template) + name_1
        assert ret.data[name_2]['url_frag'] == '{}/'.format(url_template) + name_2

    def test_spawn(self):
        """
        Test the 'spawn' command in the Clerk.
        """
        # Convenience.
        clerk = self.clerk

        # Invalid templateID.
        init_invalid = {'templateID': 'blah', 'rbs': {'imass': 1}}
        ret = clerk.spawn([init_invalid])
        assert not ret.ok
        assert ret.msg.startswith('Could not find all templates')

        # Valid templateID but invalid key name in rbs field.
        init_invalid = {'templateID': '_templateSphere', 'rbs': {'blah': 1}}
        assert not clerk.spawn([init_invalid]).ok

        # Valid templateID, valid key, but invalid data.
        init_invalid = {'templateID': '_templateSphere', 'rbs': {'position': 1}}
        assert not clerk.spawn([init_invalid]).ok

        # All parameters are now valid. This must spawn an object with ID=1
        # because this is the first ID in an otherwise pristine system.
        init_1 = {'templateID': '_templateSphere', 'rbs': {'imass': 1}}
        ret = clerk.spawn([init_1])
        assert (ret.ok, ret.data) == (True, (1, ))

        # Geometry for this object must now exist.
        print(clerk.getFragments([1]))
        assert clerk.getFragments([1]).data[1] is not None

        # Spawn two more objects with a single call.
        name_2 = '_templateSphere'
        name_3 = '_templateBox'
        init_2 = {'templateID': name_2, 'rbs': {'imass': 2}}
        init_3 = {'templateID': name_3, 'rbs': {'imass': 3}}
        ret = clerk.spawn([init_2, init_3])
        assert (ret.ok, ret.data) == (True, (2, 3))

        # Geometry for last two object must now exist as well.
        ret = clerk.getFragments([2, 3])
        assert ret.data[2] is not None
        assert ret.data[3] is not None

        # Spawn two identical objects with a single call.
        ret = clerk.spawn([init_2, init_3])
        assert (ret.ok, ret.data) == (True, (4, 5))

        # Geometry for last two object must now exist as well.
        ret = clerk.getFragments([4, 5])
        assert ret.data[4] is not None
        assert ret.data[5] is not None

        # Invalid: list of objects must not be empty.
        assert not clerk.spawn([]).ok

        # Invalid: List elements do not contain the correct data types.
        assert not clerk.spawn([name_2]).ok

        # Invalid: one template does not exist.
        assert not clerk.spawn([init_invalid, init_2]).ok

    def test_get_object_template_id(self):
        """
        Spawn two objects from different templates. Then query the template ID
        based on the object ID.
        """
        # Parameters and constants for this test.
        id_0, id_1 = 1, 2
        tID_0 = '_templateEmpty'
        tID_1 = '_templateBox'

        # Convenience.
        clerk = self.clerk

        # Spawn two objects. Their IDs must be id_0 and id_1, respectively.
        ret = clerk.spawn([{'templateID': tID_0}, {'templateID': tID_1}])
        assert (ret.ok, ret.data) == (True, (id_0, id_1))

        # Retrieve template of first object.
        ret = clerk.getTemplateID(id_0)
        assert (ret.ok, ret.data) == (True, tID_0)

        # Retrieve template of second object.
        ret = clerk.getTemplateID(id_1)
        assert (ret.ok, ret.data) == (True, tID_1)

        # Attempt to retrieve a non-existing object.
        assert not clerk.getTemplateID(100).ok

    def test_spawn_DibblerClerkSyncProblem(self):
        """
        Try to spawn a template that Clerk finds in its template database but
        that is not in Dibbler.
        """
        # Convenience.
        clerk = azrael.clerk.Clerk()

        # Mock the Dibbler instance.
        mock_dibbler = mock.create_autospec(azrael.dibbler.Dibbler)
        clerk.dibbler = mock_dibbler
        mock_dibbler.spawnTemplate.return_value = RetVal(False, 'error', None)

        # Attempt to spawn a valid template. The template exists in the
        # template database (the setup method for this test did it), but
        # because Dibbler cannot find the model data Clerk will skip it. The
        # net effect is that the spawn command must succeed but not spawn any
        # objects.
        init = {'templateID': '_templateEmpty', 'rbs': {'imass': 1}}
        ret = clerk.spawn([init])
        assert ret == (True, None, tuple())

    def test_removeObject(self):
        """
        Test the 'removeObject' command in the Clerk.

        Spawn an object and ensure it exists, then delete it and ensure it does
        not exist anymore.
        """
        # Test constants and parameters.
        objID_1, objID_2 = 1, 2

        # Convenience.
        clerk = self.clerk

        # No objects must exist at this point.
        ret = clerk.getAllObjectIDs()
        assert (ret.ok, ret.data) == (True, [])

        # Spawn two default objects.
        templateID = '_templateSphere'
        init = {'templateID': templateID}
        ret = clerk.spawn([init, init])
        assert (ret.ok, ret.data) == (True, (objID_1, objID_2))

        # Two objects must now exist.
        ret = clerk.getAllObjectIDs()
        assert ret.ok and (set(ret.data) == set([objID_1, objID_2]))

        # Delete the first object.
        assert clerk.removeObject(objID_1).ok

        # Only the second object must still exist.
        ret = clerk.getAllObjectIDs()
        assert (ret.ok, ret.data) == (True, [objID_2])

        # Deleting the same object again must silently fail.
        assert clerk.removeObject(objID_1).ok

        # Delete the second object.
        assert clerk.removeObject(objID_2).ok
        ret = clerk.getAllObjectIDs()
        assert (ret.ok, ret.data) == (True, [])

    def test_getRigidBodies(self):
        """
        Test the 'getRigidBodies' command in the Clerk.
        """
        # Test parameters and constants.
        objID_1 = 1
        objID_2 = 2
        RBS = getRigidBody
        body_1 = RBS(position=(0, 1, 2), velocityLin=(2, 4, 6))
        body_2 = RBS(position=(2, 4, 6), velocityLin=(6, 8, 10))

        # Convenience.
        clerk = self.clerk

        # Retrieve all body states --> there must be none.
        ret = clerk.getRigidBodies(None)
        assert (ret.ok, ret.data) == (True, {})

        # Retrieve the SV for a non-existing ID.
        ret = clerk.getRigidBodies([10])
        assert (ret.ok, ret.data) == (True, {10: None})

        # Spawn a new object. It must have ID=1.
        init_1 = {
            'templateID': '_templateSphere',
            'rbs': {
                'position': body_1.position,
                'velocityLin': body_1.velocityLin
            }
        }
        init_2 = {
            'templateID': '_templateSphere',
            'rbs': {
                'position': body_2.position,
                'velocityLin': body_2.velocityLin
            }
        }
        ret = clerk.spawn([init_1])
        assert (ret.ok, ret.data) == (True, (objID_1, ))

        # Retrieve the body state for a non-existing ID --> must fail.
        ret = clerk.getRigidBodies([10])
        assert (ret.ok, ret.data) == (True, {10: None})

        # Retrieve the body state for the existing ID=1.
        ret = clerk.getRigidBodies([objID_1])
        assert (ret.ok, len(ret.data)) == (True, 1)
        assert RBS(*ret.data[objID_1]['rbs']) == body_1
        assert ret == clerk.getRigidBodies(None)

        # Spawn a second object.
        ret = clerk.spawn([init_2])
        assert (ret.ok, ret.data) == (True, (objID_2, ))

        # Retrieve the state variables for both objects individually.
        for objID, ref_sv in zip([objID_1, objID_2], [body_1, body_2]):
            ret = clerk.getRigidBodies([objID])
            assert (ret.ok, len(ret.data)) == (True, 1)
            assert RBS(*ret.data[objID]['rbs']) == ref_sv

        # Retrieve the state variables for both objects at once.
        ret = clerk.getRigidBodies([objID_1, objID_2])
        assert (ret.ok, len(ret.data)) == (True, 2)
        assert RBS(*ret.data[objID_1]['rbs']) == body_1
        assert RBS(*ret.data[objID_2]['rbs']) == body_2

        # Query all of them.
        assert ret == clerk.getRigidBodies(None)

    def test_getObjectStates(self):
        """
        Test the 'getObjectStates' command in the Clerk.
        """
        # Convenience.
        clerk = self.clerk

        # Test parameters and constants.
        id_1, id_2 = 1, 2

        # Define a template for this test and upload it.
        frags = {'f1': getFragRaw(scale=2), 'f2': getFragRaw(rot=[0, 1, 0, 0])}
        body_1 = getRigidBody(cshapes={'cssphere': getCSSphere()})
        t1 = getTemplate('t1', rbs=body_1, fragments=frags)
        assert clerk.addTemplates([t1]).ok

        # Retrieve all body states --> there must be none.
        ret = clerk.getObjectStates(None)
        assert (ret.ok, ret.data) == (True, {})

        # Retrieve the states for a non-existing object.
        ret = clerk.getObjectStates([10])
        assert (ret.ok, ret.data) == (True, {10: None})

        # Create the spawn-parameters for two new objects, but only spawn the
        # first for now.
        init_1 = {
            'templateID': 't1',
        }
        init_2 = {
            'templateID': 't1',
            'rbs': {
                'position': [2, 4, 6],
                'velocityLin': [6, 8, 10]
            }
        }
        ret = clerk.spawn([init_1])
        assert (ret.ok, ret.data) == (True, (id_1, ))

        # Again: Retrieve the body state for a non-existing ID --> must fail.
        ret = clerk.getObjectStates([10])
        assert (ret.ok, ret.data) == (True, {10: None})

        # Retrieve the object state for id_1 and verify it has the correct keys.
        ret = clerk.getObjectStates([id_1])
        assert (ret.ok, len(ret.data)) == (True, 1)

        # Verify that the rigid body meta data is correct and complete.
        expected_keys = set(['scale', 'position', 'rotation',
                             'velocityLin', 'velocityRot', 'version'])
        r = ret.data[id_1]['rbs']
        assert set(r.keys()) == expected_keys
        assert r['scale'] == 1
        assert r['position'] == list(body_1.position)
        assert r['rotation'] == list(body_1.rotation)
        assert r['velocityLin'] == list(body_1.velocityLin)
        assert r['velocityRot'] == list(body_1.velocityRot)
        del r

        # Verify that the list of fragments is correct and complete.
        r = ret.data[id_1]['frag']
        assert r.keys() == frags.keys()
        for name in ('f1', 'f2'):
            assert r[name]['scale'] == frags[name].scale
            assert r[name]['position'] == list(frags[name].position)
            assert r[name]['rotation'] == list(frags[name].rotation)
        del r

        # Query all of them.
        assert clerk.getObjectStates(None) == clerk.getObjectStates([id_1])

        # Spawn the second object.
        ret = clerk.spawn([init_2])
        assert (ret.ok, ret.data) == (True, (id_2, ))

        # Retrieve the object state for id_2 and verify it has the correct keys.
        ret = clerk.getObjectStates([id_2])
        assert (ret.ok, len(ret.data)) == (True, 1)

        # Verify that the rigid body meta data is correct and complete.
        r = ret.data[id_2]['rbs']
        assert set(r.keys()) == expected_keys
        assert r['scale'] == 1
        assert r['position'] == init_2['rbs']['position']
        assert r['rotation'] == list(body_1.rotation)
        assert r['velocityLin'] == init_2['rbs']['velocityLin']
        assert r['velocityRot'] == list(body_1.velocityRot)
        del r

        # Verify that the list of fragments is correct and complete.
        r = ret.data[id_2]['frag']
        assert r.keys() == frags.keys()
        for name in ('f1', 'f2'):
            assert r[name]['scale'] == frags[name].scale
            assert r[name]['position'] == list(frags[name].position)
            assert r[name]['rotation'] == list(frags[name].rotation)
        del r

        # Query all states in a single query and verify it matches the
        # individual queries.
        ret_all = clerk.getObjectStates(None)
        ret_1 = clerk.getObjectStates([id_1])
        ret_2 = clerk.getObjectStates([id_2])
        assert ret_all.ok == ret_1.ok == ret_2.ok is True
        ret_all, ret_1, ret_2 = ret_all.data, ret_1.data, ret_2.data
        assert ret_1[id_1] == ret_all[id_1]
        assert ret_2[id_2] == ret_all[id_2]

    def test_set_force(self):
        """
        Set and retrieve force and torque values.
        """
        # Reset the SV database and instantiate a Leonard.
        leo = getLeonard()

        # Parameters and constants for this test.
        id_1 = 1
        force = np.array([1, 2, 3], np.float64).tolist()
        relpos = np.array([4, 5, 6], np.float64).tolist()

        # Convenience.
        clerk = self.clerk

        # Spawn a new object. It must have ID=1.
        templateID = '_templateSphere'
        ret = clerk.spawn([{'templateID': templateID}])
        assert (ret.ok, ret.data) == (True, (id_1, ))

        # Apply the force.
        assert clerk.setForce(id_1, force, relpos).ok

        leo.processCommandsAndSync()
        tmp = leo.totalForceAndTorque(id_1)
        assert np.array_equal(tmp[0], force)
        assert np.array_equal(tmp[1], np.cross(relpos, force))

    def test_controlParts_invalid_commands(self):
        """
        Send invalid control commands to object.
        """
        # Parameters and constants for this test.
        objID_1, objID_2 = 1, 2
        templateID_1 = '_templateSphere'

        # Convenience.
        clerk = self.clerk

        # Create a fake object. We will not need the actual object but other
        # commands used here depend on one to exist.
        ret = clerk.spawn([{'templateID': templateID_1}])
        assert (ret.ok, ret.data) == (True, (objID_1, ))

        # Create commands for a Booster and a Factory.
        cmd_b = {'0': aztypes.CmdBooster(force=0.2)}
        cmd_f = {'0': aztypes.CmdFactory(exit_speed=0.5)}

        # Call 'controlParts'. This must fail because the template for objID_1
        # has neither boosters nor factories.
        assert not clerk.controlParts(objID_1, cmd_b, {}).ok

        # Must fail: object has no factory.
        assert not clerk.controlParts(objID_1, {}, cmd_f).ok

        # Must fail: object still has neither a booster nor a factory.
        assert not clerk.controlParts(objID_1, cmd_b, cmd_f).ok

        # ---------------------------------------------------------------------
        # Create a template with one booster and one factory. Then send
        # commands to them.
        # ---------------------------------------------------------------------

        # Define the Booster and Factory parts.
        boosters = {
            '0': aztypes.Booster(pos=(0, 0, 0), direction=(0, 0, 1),
                               minval=0, maxval=0.5, force=0)
        }
        factories = {
            '0': aztypes.Factory(pos=(0, 0, 0), direction=(0, 0, 1),
                               templateID='_templateBox', exit_speed=(0, 1))
        }

        # Define a new template, add it to Azrael, and spawn an instance.
        temp = getTemplate('t1',
                           boosters=boosters,
                           factories=factories)
        assert clerk.addTemplates([temp]).ok
        ret = clerk.spawn([{'templateID': temp.aid}])
        assert (ret.ok, ret.data) == (True, (objID_2, ))

        # Tell each factory to spawn an object.
        cmd_b = {'0': aztypes.CmdBooster(force=0.5)}
        cmd_f = {'0': aztypes.CmdFactory(exit_speed=0.5)}

        # Valid: Clerk must accept these commands.
        assert clerk.controlParts(objID_2, cmd_b, cmd_f).ok

    def test_controlParts_Boosters_notmoving(self):
        """
        Create a template with boosters and send control commands to it.

        The parent object does not move in the world coordinate system.
        """
        # Reset the SV database and instantiate a Leonard.
        leo = getLeonard()

        # Parameters and constants for this test.
        objID_1 = 1

        # Convenience.
        clerk = self.clerk

        # ---------------------------------------------------------------------
        # Define an object with a booster and spawn it.
        # ---------------------------------------------------------------------

        # Constants for the new template object.
        dir_0 = np.array([1, 0, 0], np.float64)
        dir_1 = np.array([0, 1, 0], np.float64)
        pos_0 = np.array([1, 1, -1], np.float64)
        pos_1 = np.array([-1, -1, 0], np.float64)

        # Define two boosters.
        boosters = {
            '0': aztypes.Booster(pos=pos_0, direction=dir_0,
                               minval=0, maxval=0.5, force=0),
            '1': aztypes.Booster(pos=pos_1, direction=dir_1,
                               minval=0, maxval=0.5, force=0)
        }

        # Define a new template with two boosters and add it to Azrael.
        temp = getTemplate('t1', boosters=boosters)
        assert clerk.addTemplates([temp]).ok

        # Spawn an instance of the template.
        ret = clerk.spawn([{'templateID': temp.aid}])
        assert (ret.ok, ret.data) == (True, (objID_1, ))
        del ret, temp

        # ---------------------------------------------------------------------
        # Engage the boosters and verify the total force exerted on the object.
        # ---------------------------------------------------------------------

        # Create the commands to activate both boosters with a different force.
        forcemag_0, forcemag_1 = 0.2, 0.4
        cmd_b = {
            '0': aztypes.CmdBooster(force=forcemag_0),
            '1': aztypes.CmdBooster(force=forcemag_1)
        }

        # Send booster commands to Clerk.
        assert clerk.controlParts(objID_1, cmd_b, {}).ok
        leo.processCommandsAndSync()

        # Manually compute the total force and torque exerted by the boosters.
        forcevec_0, forcevec_1 = forcemag_0 * dir_0, forcemag_1 * dir_1
        tot_force = forcevec_0 + forcevec_1
        tot_torque = np.cross(pos_0, forcevec_0) + np.cross(pos_1, forcevec_1)

        # Query the torque and force from Azrael and verify they are correct.
        tmp = leo.totalForceAndTorque(objID_1)
        assert np.array_equal(tmp[0], tot_force)
        assert np.array_equal(tmp[1], tot_torque)

        # Send an empty command. The total force and torque must not change.
        assert clerk.controlParts(objID_1, {}, {}).ok
        leo.processCommandsAndSync()
        tmp = leo.totalForceAndTorque(objID_1)
        assert np.array_equal(tmp[0], tot_force)
        assert np.array_equal(tmp[1], tot_torque)

    def test_controlParts_Factories_notmoving(self):
        """
        Create a template with factories and let them spawn objects.

        The parent object does not move in the world coordinate system.
        """
        # Convenience.
        clerk = self.clerk

        # ---------------------------------------------------------------------
        # Create a template with two factories and spawn it.
        # ---------------------------------------------------------------------

        # Constants for the new template object.
        objID_1 = 1
        dir_0 = np.array([1, 0, 0], np.float64)
        dir_1 = np.array([0, 1, 0], np.float64)
        pos_0 = np.array([1, 1, -1], np.float64)
        pos_1 = np.array([-1, -1, 0], np.float64)

        # Define a new object with two factory parts. The Factory parts are
        # named tuples passed to addTemplates. The user must assign the partIDs
        # manually.
        factories = {
            '0': aztypes.Factory(pos=pos_0, direction=dir_0,
                               templateID='_templateBox',
                               exit_speed=[0.1, 0.5]),
            '1': aztypes.Factory(pos=pos_1, direction=dir_1,
                               templateID='_templateSphere',
                               exit_speed=[1, 5])
        }

        # Add the template to Azrael and spawn one instance.
        temp = getTemplate('t1', factories=factories)
        assert clerk.addTemplates([temp]).ok
        ret = clerk.spawn([{'templateID': temp.aid}])
        assert (ret.ok, ret.data) == (True, (objID_1, ))
        del ret, temp, factories

        # ---------------------------------------------------------------------
        # Instruct factories to create an object with a specific exit velocity.
        # ---------------------------------------------------------------------

        # Create the commands to let each factory spawn an object.
        exit_speed_0, exit_speed_1 = 0.2, 2
        cmd_f = {
            '0': aztypes.CmdFactory(exit_speed=exit_speed_0),
            '1': aztypes.CmdFactory(exit_speed=exit_speed_1)
        }

        # Send the commands and ascertain that the returned object IDs now
        # exist in the simulation. These IDs must be '2' and '3'.
        ok, _, spawnedIDs = clerk.controlParts(objID_1, {}, cmd_f)
        id_2, id_3 = 2, 3
        assert (ok, spawnedIDs) == (True, [id_2, id_3])
        del spawnedIDs

        # Query the state variables of the objects spawned by the factories.
        ret = clerk.getRigidBodies([id_2, id_3])
        assert (ret.ok, len(ret.data)) == (True, 2)

        # Determine which body was spawned by which factory based on their
        # position. We do this by looking at their initial position which
        # *must* match one of the parents.
        body_2, body_3 = ret.data[id_2]['rbs'], ret.data[id_3]['rbs']
        if np.allclose(body_2.position, pos_1):
            body_2, body_3 = body_3, body_2

        # Ensure the position, velocity, and rotation of the spawned objects
        # are correct.
        assert np.allclose(body_2.velocityLin, exit_speed_0 * dir_0)
        assert np.allclose(body_2.position, pos_0)
        assert np.allclose(body_2.rotation, [0, 0, 0, 1])
        assert np.allclose(body_3.velocityLin, exit_speed_1 * dir_1)
        assert np.allclose(body_3.position, pos_1)
        assert np.allclose(body_3.rotation, [0, 0, 0, 1])

    def test_controlParts_Factories_moving(self):
        """
        Create a template with factories and send control commands to them.

        In this test the parent object moves at a non-zero velocity.
        """
        clerk = self.clerk

        # Parameters and constants for this test.
        objID_1, objID_2, objID_3 = 1, 2, 3
        pos_parent = np.array([1, 2, 3], np.float64)
        vel_parent = np.array([4, 5, 6], np.float64)
        dir_0 = np.array([1, 0, 0], np.float64)
        dir_1 = np.array([0, 1, 0], np.float64)
        pos_0 = np.array([1, 1, -1], np.float64)
        pos_1 = np.array([-1, -1, 0], np.float64)

        # State variables for parent object.
        body = getRigidBody(position=pos_parent, velocityLin=vel_parent)

        # ---------------------------------------------------------------------
        # Create a template with two factories and spawn it.
        # ---------------------------------------------------------------------

        # Define factory parts.
        factories = {
            '0': aztypes.Factory(pos=pos_0, direction=dir_0,
                               templateID='_templateBox',
                               exit_speed=[0.1, 0.5]),
            '1': aztypes.Factory(pos=pos_1, direction=dir_1,
                               templateID='_templateSphere',
                               exit_speed=[1, 5])
        }

        # Define a template with two factories, add it to Azrael, and spawn it.
        temp = getTemplate('t1', factories=factories)
        init = {
            'templateID': temp.aid,
            'rbs': {'position': body.position, 'velocityLin': body.velocityLin}
        }

        assert clerk.addTemplates([temp]).ok
        ret = clerk.spawn([init])
        assert (ret.ok, ret.data) == (True, (objID_1, ))
        del temp, ret, factories, body

        # ---------------------------------------------------------------------
        # Instruct factories to create an object with a specific exit velocity.
        # ---------------------------------------------------------------------

        # Create the commands to let each factory spawn an object.
        exit_speed_0, exit_speed_1 = 0.2, 2
        cmd_f = {
            '0': aztypes.CmdFactory(exit_speed=exit_speed_0),
            '1': aztypes.CmdFactory(exit_speed=exit_speed_1),
        }

        # Send the commands and ascertain that the returned object IDs now
        # exist in the simulation.
        ret = clerk.controlParts(objID_1, {}, cmd_f)
        assert ret.ok and (len(ret.data) == 2)
        assert ret.data == [objID_2, objID_3]

        # Query the state variables of the objects spawned by the factories.
        ret = clerk.getRigidBodies([objID_2, objID_3])
        assert (ret.ok, len(ret.data)) == (True, 2)

        # Determine which body was spawned by which factory based on their
        # position. We do this by looking at their initial position which
        # *must* match one of the parents.
        body_2, body_3 = ret.data[objID_2]['rbs'], ret.data[objID_3]['rbs']
        if np.allclose(body_2.position, pos_1 + pos_parent):
            body_2, body_3 = body_3, body_2

        # Ensure the position/velocity/rotation are correct.
        assert np.allclose(body_2.velocityLin, exit_speed_0 * dir_0 + vel_parent)
        assert np.allclose(body_2.position, pos_0 + pos_parent)
        assert np.allclose(body_2.rotation, [0, 0, 0, 1])
        assert np.allclose(body_3.velocityLin, exit_speed_1 * dir_1 + vel_parent)
        assert np.allclose(body_3.position, pos_1 + pos_parent)
        assert np.allclose(body_3.rotation, [0, 0, 0, 1])

    def test_controlParts_Boosters_and_Factories_move_and_rotated(self):
        """
        Create a template with boosters and factories. Then send control
        commands to them and ensure the applied forces, torques, and
        spawned objects are correct.

        In this test the parent object moves and is oriented away from its
        default.
        """
        # Reset the SV database and instantiate a Leonard.
        leo = getLeonard()

        # Parameters and constants for this test.
        objID_1, objID_2, objID_3 = 1, 2, 3
        pos_parent = np.array([1, 2, 3], np.float64)
        vel_parent = np.array([4, 5, 6], np.float64)

        # Part positions relative to parent.
        dir_0 = np.array([0, 0, +2], np.float64)
        dir_1 = np.array([0, 0, -1], np.float64)
        pos_0 = np.array([0, 0, +3], np.float64)
        pos_1 = np.array([0, 0, -4], np.float64)

        # Describes a rotation of 180 degrees around x-axis.
        orient_parent = [1, 0, 0, 0]

        # Part position in world coordinates if the parent is rotated by 180
        # degrees around the x-axis. The normalisation of the direction is
        # necessary because the parts will automatically normalise all
        # direction vectors, including dir_0 and dir_1 which are not unit
        # vectors.
        dir_0_out = np.array(-dir_0) / np.sum(abs(dir_0))
        dir_1_out = np.array(-dir_1) / np.sum(abs(dir_1))
        pos_0_out = np.array(-pos_0)
        pos_1_out = np.array(-pos_1)

        # State variables for parent object. This one has a position and speed,
        # and is rotate 180 degrees around the x-axis. This means the x-values
        # of all forces (boosters) and exit speeds (factory spawned objects)
        # must be inverted.
        body = getRigidBody(position=pos_parent,
                            velocityLin=vel_parent,
                            rotation=orient_parent)
        # Convenience.
        clerk = self.clerk

        # ---------------------------------------------------------------------
        # Define and spawn a template with two boosters and two factories.
        # ---------------------------------------------------------------------

        # Define the Booster and Factory parts.
        boosters = {
            '0': aztypes.Booster(pos=pos_0, direction=dir_0,
                               minval=0, maxval=0.5, force=0),
            '1': aztypes.Booster(pos=pos_1, direction=dir_1,
                               minval=0, maxval=1.0, force=0)
        }
        factories = {
            '0': aztypes.Factory(pos=pos_0, direction=dir_0,
                               templateID='_templateBox',
                               exit_speed=[0.1, 0.5]),
            '1': aztypes.Factory(pos=pos_1, direction=dir_1,
                               templateID='_templateSphere',
                               exit_speed=[1, 5])
        }

        # Define the template, add it to Azrael, and spawn one instance.
        temp = getTemplate('t1', boosters=boosters,  factories=factories)
        assert clerk.addTemplates([temp]).ok

        init = {
            'templateID': temp.aid,
            'rbs': {
                'position': body.position,
                'rotation': body.rotation,
                'velocityLin': body.velocityLin
            }
        }
        ret = clerk.spawn([init])
        assert (ret.ok, ret.data) == (True, (objID_1, ))
        del boosters, factories, temp

        # ---------------------------------------------------------------------
        # Activate booster and factories. Then verify that boosters apply the
        # correct force and the spawned objects have the correct body state.
        # ---------------------------------------------------------------------

        # Create the commands to let each factory spawn an object.
        exit_speed_0, exit_speed_1 = 0.2, 2
        forcemag_0, forcemag_1 = 0.2, 0.4
        cmd_b = {
            '0': aztypes.CmdBooster(force=forcemag_0),
            '1': aztypes.CmdBooster(force=forcemag_1),
        }
        cmd_f = {
            '0': aztypes.CmdFactory(exit_speed=exit_speed_0),
            '1': aztypes.CmdFactory(exit_speed=exit_speed_1),
        }

        # Send the commands and ascertain that the returned object IDs now
        # exist in the simulation. These IDs must be '2' and '3'.
        ret = clerk.controlParts(objID_1, cmd_b, cmd_f)
        assert (ret.ok, ret.data) == (True, [objID_2, objID_3])
        del ret

        # Query the state variables of the objects spawned by the factories.
        ret = clerk.getRigidBodies([objID_2, objID_3])
        assert (ret.ok, len(ret.data)) == (True, 2)

        # Determine which body was spawned by which factory based on their
        # position. We do this by looking at their initial position which
        # *must* match one of the parents.
        body_2, body_3 = ret.data[objID_2]['rbs'], ret.data[objID_3]['rbs']
        if np.allclose(body_2.position, pos_1_out + pos_parent):
            body_2, body_3 = body_3, body_2

        # Verify the positions and velocities are correct.
        AC = np.allclose
        assert AC(body_2.velocityLin, exit_speed_0 * dir_0_out + vel_parent)
        assert AC(body_2.position, pos_0_out + pos_parent)
        assert AC(body_2.rotation, orient_parent)
        assert AC(body_3.velocityLin, exit_speed_1 * dir_1_out + vel_parent)
        assert AC(body_3.position, pos_1_out + pos_parent)
        assert AC(body_3.rotation, orient_parent)

        # Manually compute the total force and torque exerted by the boosters.
        forcevec_0, forcevec_1 = forcemag_0 * dir_0_out, forcemag_1 * dir_1_out
        tot_force = forcevec_0 + forcevec_1
        tot_torque = (np.cross(pos_0_out, forcevec_0) +
                      np.cross(pos_1_out, forcevec_1))

        # Let Leonard sync itself to Azrael and then query the torque and force
        # it applies to the objects due to the activated boosters.
        leo.processCommandsAndSync()
        tmp = leo.totalForceAndTorque(objID_1)
        assert np.array_equal(tmp[0], tot_force)
        assert np.array_equal(tmp[1], tot_torque)

    def test_get_all_objectids(self):
        """
        Test getAllObjects.
        """
        # Parameters and constants for this test.
        objID_1, objID_2 = 1, 2
        templateID = '_templateSphere'

        # Convenience.
        clerk = self.clerk

        # So far no objects have been spawned.
        ret = clerk.getAllObjectIDs()
        assert (ret.ok, ret.data) == (True, [])

        # Spawn a new object.
        ret = clerk.spawn([{'templateID': templateID}])
        assert (ret.ok, ret.data) == (True, (objID_1, ))

        # The object list must now contain the ID of the just spawned object.
        ret = clerk.getAllObjectIDs()
        assert (ret.ok, ret.data) == (True, [objID_1])

        # Spawn another object.
        ret = clerk.spawn([{'templateID': templateID}])
        assert (ret.ok, ret.data) == (True, (objID_2, ))

        # The object list must now contain the ID of both spawned objects.
        ret = clerk.getAllObjectIDs()
        assert (ret.ok, ret.data) == (True, [objID_1, objID_2])

    def test_getFragments(self):
        """
        Spawn two objects and query their fragment geometries.
        """
        # Convenience.
        clerk = self.clerk

        # Raw object: specify vertices, UV, and texture (RGB) values directly.
        body_1 = getRigidBody(position=[1, 2, 3])
        body_2 = getRigidBody(position=[4, 5, 6])

        # Put both fragments into a valid list of FragMetas.
        frags = {'f_raw': getFragRaw(), 'f_dae': getFragDae()}

        # Add a valid template with the just specified fragments and verify the
        # upload worked.
        temp = getTemplate('foo', rbs=body_1, fragments=frags)
        assert clerk.addTemplates([temp]).ok
        assert clerk.getTemplates([temp.aid]).ok

        # Attempt to query the geometry of a non-existing object.
        assert clerk.getFragments([123]) == (True, None, {123: None})

        init_1 = {
            'templateID': temp.aid,
            'rbs': {'position': body_1.position}
        }
        init_2 = {
            'templateID': temp.aid,
            'rbs': {'position': body_2.position}
        }

        # Spawn two objects from the previously added template.
        ret = clerk.spawn([init_1, init_2])
        assert ret.ok
        objID_1, objID_2 = ret.data

        def _verify(_ret, _objID):
            _ret = _ret[_objID]
            _objID = str(_objID)

            # The object must have two fragments, an 'f_raw' with type 'RAW'
            # and an 'f_dae' with type 'DAE'.
            _url_inst = config.url_instances + '/'
            assert _ret['f_raw']['fragtype'] == 'RAW'
            assert _ret['f_raw']['url_frag'] == _url_inst + _objID + '/f_raw'
            assert _ret['f_dae']['fragtype'] == 'DAE'
            assert _ret['f_dae']['url_frag'] == _url_inst + _objID + '/f_dae'
            return True

        # Query and verify the geometry of the first instance.
        ret = clerk.getFragments([objID_1])
        assert ret.ok and _verify(ret.data, objID_1)

        # Query and verify the geometry of the second instance.
        ret = clerk.getFragments([objID_2])
        assert ret.ok and _verify(ret.data, objID_2)

        # Query both instances at once and verify them.
        ret = clerk.getFragments([objID_1, objID_2])
        assert ret.ok and _verify(ret.data, objID_1)
        assert ret.ok and _verify(ret.data, objID_2)

        # Delete first and query again.
        assert clerk.removeObject(objID_1).ok
        ret = clerk.getFragments([objID_1, objID_2])
        assert ret.ok
        assert ret.data[objID_1] is None
        assert _verify(ret.data, objID_2)

    def test_instanceDB_fragment_version(self):
        """
        Spawn two objects, modify their geometries, and verify that the
        'version' flag changes accordingly.
        """
        # Convenience.
        clerk = self.clerk

        # Add a valid template and verify it now exists in Azrael.
        temp = getTemplate('foo', fragments={'bar': getFragRaw()})
        assert clerk.addTemplates([temp]).ok

        # Spawn two objects from the previously defined template.
        init = {'templateID': temp.aid}
        ret = clerk.spawn([init, init])
        assert ret.ok and (len(ret.data) == 2)
        objID0, objID1 = ret.data

        # Query the State Vectors for both objects.
        ret = clerk.getRigidBodies([objID0, objID1])
        assert ret.ok and (set((objID0, objID1)) == set(ret.data.keys()))
        ref_version = ret.data[objID0]['rbs'].version

        # Modify the 'bar' fragment of objID0 and verify that exactly one
        # geometry was updated.
        cmd = {objID0: {'bar': getFragRaw()._asdict()}}
        assert clerk.setFragments(cmd).ok

        # Verify that the new 'version' flag is now different.
        ret = clerk.getRigidBodies([objID0])
        assert ret.ok
        assert ref_version != ret.data[objID0]['rbs'].version

        # Verify further that the version attribute of objID1 is unchanged.
        ret = clerk.getRigidBodies([objID1])
        assert ret.ok
        assert ref_version == ret.data[objID1]['rbs'].version

    def test_setFragments(self):
        """
        Spawn three objects and modify the geometries of two.
        """
        # Convenience.
        clerk = self.clerk

        # Add a valid template and verify it now exists in Azrael.
        temp = getTemplate('t1', fragments={'foo': getFragRaw(), 'bar': getFragDae()})
        assert clerk.addTemplates([temp]).ok

        # Spawn two objects from the previously defined template.
        init = {'templateID': temp.aid}
        ret = clerk.spawn([init, init, init])
        assert ret.ok and (len(ret.data) == 3)
        id_1, id_2, id_3 = ret.data

        # Modify the 'bar'- and 'foo' fragment of id_1 and of id_3,
        # respectively, by swapping their types.
        cmd = {id_1: {'foo': getFragDae()._asdict()},
               id_3: {'bar': getFragRaw()._asdict()}}
        assert clerk.setFragments(cmd).ok

        # Fetch the fragments.
        ret = clerk.getFragments([id_1, id_2, id_3])
        assert ret.ok

        # Verify that the changes reflect in the new fragment types.
        assert ret.data[id_2]['foo']['fragtype'] == 'RAW'
        assert ret.data[id_2]['bar']['fragtype'] == 'DAE'

        assert ret.data[id_1]['foo']['fragtype'] == 'DAE'
        assert ret.data[id_1]['bar']['fragtype'] == 'DAE'

        assert ret.data[id_3]['foo']['fragtype'] == 'RAW'
        assert ret.data[id_3]['bar']['fragtype'] == 'RAW'

    def test_setFragments_partial(self):
        """
        Spawn three objects and modify parts of the geometries only.
        """
        # Convenience.
        clerk = self.clerk

        # Add a valid template and verify it now exists in Azrael.
        fraw, fdae = getFragRaw(), getFragDae()
        temp = getTemplate('t1', fragments={'foo': fraw, 'bar': fdae})
        assert clerk.addTemplates([temp]).ok

        # Spawn three objects from the previously defined template.
        init = {'templateID': temp.aid}
        ret = clerk.spawn([init, init, init])
        assert ret.ok and (len(ret.data) == 3)
        id_1, id_2, id_3 = ret.data

        # Specify what to update.
        cmd = {id_1: {'foo': {'scale': 2, 'position': (0, 1, 2)}},
               id_3: {'bar': getFragRaw()._asdict()}}
        assert clerk.setFragments(cmd).ok

        # Fetch the fragments.
        ret = clerk.getFragments([id_1, id_2, id_3])
        assert ret.ok

        # Verify that the changes reflect in the new fragment types.
        r1 = ret.data[id_1]
        assert r1['foo']['scale'] == 2
        assert r1['foo']['position'] == (0, 1, 2)
        assert r1['foo']['rotation'] == fraw.rotation
        assert r1['foo']['fragtype'] == fraw.fragtype
        assert r1['bar']['scale'] == fdae.scale
        assert r1['bar']['position'] == fdae.position
        assert r1['bar']['rotation'] == fdae.rotation
        assert r1['bar']['fragtype'] == fdae.fragtype

        r2 = ret.data[id_2]
        assert r2['foo']['scale'] == fraw.scale
        assert r2['foo']['position'] == fraw.position
        assert r2['foo']['rotation'] == fraw.rotation
        assert r2['foo']['fragtype'] == fraw.fragtype
        assert r2['bar']['scale'] == fdae.scale
        assert r2['bar']['position'] == fdae.position
        assert r2['bar']['rotation'] == fdae.rotation
        assert r2['bar']['fragtype'] == fdae.fragtype

        r3 = ret.data[id_3]
        assert r3['foo']['scale'] == fraw.scale
        assert r3['foo']['position'] == fraw.position
        assert r3['foo']['rotation'] == fraw.rotation
        assert r3['foo']['fragtype'] == fraw.fragtype
        assert r3['bar']['scale'] == fdae.scale
        assert r3['bar']['position'] == fdae.position
        assert r3['bar']['rotation'] == fdae.rotation
        assert r3['bar']['fragtype'] == fraw.fragtype

    def test_setFragments_partial_bug1(self):
        """
        If the bug is present then a partial update that does not include the
        fragment geometry itself would actually delete the geometry in Dibbler.
        This test verifies that Dibbler is called with the correct arguments to
        prevent that.
        """
        # Convenience.
        clerk = azrael.clerk.Clerk()

        # Add a valid template and verify it now exists in Azrael.
        fraw, fdae = getFragRaw(), getFragDae()
        temp = getTemplate('t1', fragments={'foo': fraw, 'bar': fdae})
        assert clerk.addTemplates([temp]).ok

        # Spawn one objects from the previously defined template.
        init = {'templateID': temp.aid}
        ret = clerk.spawn([init])
        assert ret.ok and (len(ret.data) == 1)
        id_1, = ret.data

        # Install a mock for Dibbler with an 'addTemplate' function that
        # always succeeds.
        mock_dibbler = mock.create_autospec(azrael.dibbler.Dibbler)
        clerk.dibbler = mock_dibbler

        # Specify what to update.
        cmd = {id_1: {'foo': {'scale': 2, 'position': (0, 1, 2)},
                      'bar': getFragRaw()._asdict()}}
        assert clerk.setFragments(cmd).ok

        # Verify that 'dibbler.updateFragments' was called exactly once for id_0
        assert mock_dibbler.updateFragments.call_count == 1
        args = mock_dibbler.updateFragments.call_args[0]
        assert args[0] == id_1

        # Verify that the fragment dictionary did not contain 'foo' because it
        # did not update the geometry itself.
        assert set(args[1].keys()) == {'bar'}

    def test_setFragments_partial_bug2(self):
        """
        Updating the fragment state without altering the geometry must not
        modify the 'version' value.
        """
        # Convenience.
        clerk = azrael.clerk.Clerk()

        # Add and spawn a template.
        fraw, fdae = getFragRaw(), getFragDae()
        temp = getTemplate('t1', fragments={'foo': fraw, 'bar': fdae})
        assert clerk.addTemplates([temp]).ok
        ret = clerk.spawn([{'templateID': temp.aid}])
        assert ret.ok and (len(ret.data) == 1)
        id_1 = ret.data[0]

        # Fetch the current version of the fragments.
        ret = clerk.getObjectStates([id_1])
        assert ret.ok
        version = ret.data[id_1]['rbs']['version']

        # Modify the scale value. This must not alter the version.
        assert clerk.setFragments({id_1: {'foo': {'scale': 10}}}).ok
        ret = clerk.getObjectStates([id_1])
        assert ret.ok
        assert ret.data[id_1]['rbs']['version'] == version
        assert ret.data[id_1]['frag']['foo']['scale'] == 10

        # Modify the scale value of the first fragment and replace the geometry
        # of the second. This must change the version.
        new_val = {id_1: {'foo': {'scale': 20}, 'bar': fdae._asdict()}}
        assert clerk.setFragments(new_val).ok
        ret = clerk.getObjectStates([id_1])
        assert ret.ok
        assert ret.data[id_1]['rbs']['version'] != version
        assert ret.data[id_1]['frag']['foo']['scale'] == 20

    def test_setFragments_partial_eclectic(self):
        """
        Update fragment state data only (ie not the geometry itself). This test
        suite covers several corner cases to ensure the partial updates work
        correctly when eg fragments or objects do not exist.
        """
        clerk = self.clerk

        # Attempt to update the fragment state of non-existing objects.
        newStates = {2: {'1': {'scale': 2.2}}}
        assert not clerk.setFragments(newStates).ok

        # Define a new template with one fragment.
        t1 = getTemplate('t1', fragments={'foo': getFragRaw()})

        # Add the template to Azrael and spawn two instances.
        assert clerk.addTemplates([t1]).ok
        init = {'templateID': t1.aid}
        ok, _, (objID_1, objID_2) = clerk.spawn([init, init])
        assert ok

        def checkFragState(scale_1, pos_1, rot_1, scale_2, pos_2, rot_2):
            """
            Convenience function to verify the fragment states of
            objID_1 and objID_2 (defined in outer scope). This function
            assumes there are two objects and each has one fragment with
            name 'foo'.
            """
            # Query the object states for both objects.
            ret = clerk.getObjectStates([objID_1, objID_2])
            assert ret.ok and (len(ret.data) == 2)

            # Extract the one and only fragment of each object.
            _frag_1 = ret.data[objID_1]['frag']['foo']
            _frag_2 = ret.data[objID_2]['frag']['foo']

            # Compile the expected values into a dictionary.
            ref_1 = {'scale': scale_1, 'position': pos_1, 'rotation': rot_1}
            ref_2 = {'scale': scale_2, 'position': pos_2, 'rotation': rot_2}

            # Verify the fragments have the expected values.
            assert _frag_1 == ref_1
            assert _frag_2 == ref_2

        def getCmd(scale, pos, rot):
            """
            Return dictionary with the constituent entries.

            This is a convenience function only to make this test more
            readable.
            """
            return {'scale': scale, 'position': pos, 'rotation': rot}

        # All fragments must initially be at the center.
        checkFragState(1, [0, 0, 0], [0, 0, 0, 1],
                       1, [0, 0, 0], [0, 0, 0, 1])

        # Update and verify the fragment states of the second object.
        newStates = {objID_2: {'foo': getCmd(2.2, [1, 2, 3], [1, 0, 0, 0])}}
        assert clerk.setFragments(newStates).ok
        checkFragState(1, [0, 0, 0], [0, 0, 0, 1],
                       2.2, [1, 2, 3], [1, 0, 0, 0])

        # Modify the fragment states of two instances at once.
        newStates = {
            objID_1: {'foo': getCmd(3.3, [1, 2, 4], [2, 0, 0, 0])},
            objID_2: {'foo': getCmd(4.4, [1, 2, 5], [0, 3, 0, 0])}
        }
        assert clerk.setFragments(newStates).ok
        checkFragState(3.3, [1, 2, 4], [2, 0, 0, 0],
                       4.4, [1, 2, 5], [0, 3, 0, 0])

        # Attempt to update the fragment state of two objects. However, this
        # time only one of the objects actually exists. The expected behaviour
        # is that the command returns an error yet correctly updates the
        # fragment state of the existing object.
        newStates = {
            1000000: {'foo': getCmd(5, [5, 5, 5], [5, 5, 5, 5])},
            objID_2: {'foo': getCmd(5, [5, 5, 5], [5, 5, 5, 5])}
        }
        assert not clerk.setFragments(newStates).ok
        checkFragState(3.3, [1, 2, 4], [2, 0, 0, 0],
                       5.0, [5, 5, 5], [5, 5, 5, 5])

        # Attempt to update a non-existing fragment.
        newStates = {
            objID_2: {'blah': getCmd(6, [6, 6, 6], [6, 6, 6, 6])}
        }
        assert not clerk.setFragments(newStates).ok
        checkFragState(3.3, [1, 2, 4], [2, 0, 0, 0],
                       5.0, [5, 5, 5], [5, 5, 5, 5])

        # Attempt to update several fragments in one object. However, not all
        # fragment IDs are valid. The expected behaviour is that none of the
        # fragments was updated.
        newStates = {
            objID_2: {'foo': getCmd(7, [7, 7, 7], [7, 7, 7, 7]),
                      'blah': getCmd(8, [8, 8, 8], [8, 8, 8, 8])}
        }
        assert not clerk.setFragments(newStates).ok
        checkFragState(3.3, [1, 2, 4], [2, 0, 0, 0],
                       5.0, [5, 5, 5], [5, 5, 5, 5])

        # Update the fragments twice with the exact same data. This triggered a
        # bug at one point that must not occur anymore.
        newStates = {objID_2: {'foo': getCmd(9, [9, 9, 9], [9, 9, 9, 9])}}
        assert clerk.setFragments(newStates).ok
        assert clerk.setFragments(newStates).ok

    def test_fragments_end2end(self):
        """
        Integration test: create a live system, add a template with two
        fragments, spawn it, query it, very its geometry, alter its
        geometry, and verify again.
        """
        clerk = self.clerk
        web = azrael.web.WebServer()
        web.start()

        def checkFragState(objID, name_1, scale_1, pos_1, rot_1,
                           name_2, scale_2, pos_2, rot_2):
            """
            Convenience function to verify the fragment states of ``objID``.
            This function assumes the object has exactly two fragments.
            """
            # Query the object states for both objects.
            ret = clerk.getObjectStates([objID])
            assert ret.ok and (len(ret.data) == 1)

            # Extract the fragments and verify there are the two.
            _frags = ret.data[objID]['frag']
            assert len(_frags) == 2

            # Verify the correct fragment names are present.
            assert {name_1, name_2} == set(_frags.keys())

            # Compile the expected values into a dictionary.
            ref_1 = {'scale': scale_1, 'position': pos_1, 'rotation': rot_1}
            ref_2 = {'scale': scale_2, 'position': pos_2, 'rotation': rot_2}

            # Verify the fragments have the expected values.
            assert _frags[name_1] == ref_1
            assert _frags[name_2] == ref_2
            del ret, _frags

        def getCmd(scale, pos, rot):
            """
            Return dictionary with the constituent entries.

            This is a convenience function only to make this test more
            readable.
            """
            return {'scale': scale, 'position': pos, 'rotation': rot}

        # Create two fragments.
        f_raw = getFragRaw()
        f_dae = getFragDae()
        frags = {'10': f_raw, 'test': f_dae}

        t1 = getTemplate('t1', fragments=frags)
        assert clerk.addTemplates([t1]).ok
        ret = clerk.spawn([{'templateID': t1.aid}])
        assert ret.ok
        objID = ret.data[0]

        # Query the state and verify it has as many FragmentState
        # vectors as it has fragments.
        ret = clerk.getObjectStates([objID])
        assert ret.ok
        ret_frags = ret.data[objID]['frag']
        assert len(ret_frags) == len(frags)

        # Same as before, but this time get all of them.
        assert clerk.getObjectStates(None) == ret

        # Verify the fragment _states_ themselves.
        checkFragState(objID,
                       '10', 1, [0, 0, 0], [0, 0, 0, 1],
                       'test', 1, [0, 0, 0], [0, 0, 0, 1])

        # Modify the _state_ of both fragments and verify it worked.
        newStates = {
            objID: {
                '10': getCmd(7, [7, 7, 7], [7, 7, 7, 7]),
                'test': getCmd(8, [8, 8, 8], [8, 8, 8, 8])}
        }
        assert clerk.setFragments(newStates).ok
        checkFragState(objID,
                       '10', 7, [7, 7, 7], [7, 7, 7, 7],
                       'test', 8, [8, 8, 8], [8, 8, 8, 8])

        # Query the fragment _geometries_.
        ret = clerk.getFragments([objID])
        assert ret.ok
        data = ret.data[objID]
        del ret

        def _download(url):
            for ii in range(10):
                try:
                    return requests.get(url).content
                except (requests.exceptions.HTTPError,
                        requests.exceptions.ConnectionError):
                    time.sleep(0.1)
            assert False

        # Download the 'RAW' file and verify its content is correct.
        base_url = 'http://{}:{}'.format(
            azrael.config.addr_webserver, azrael.config.port_webserver)
        url = base_url + data['10']['url_frag'] + '/model.json'
        tmp = _download(url)
        tmp = json.loads(tmp.decode('utf8'))
        assert FragRaw(**tmp) == f_raw.fragdata

        # Download and verify the dae file. Note that the file name itself
        # matches the name of the fragment (ie. 'test'), *not* the name of the
        # original Collada file ('cube.dae').
        url = base_url + data['test']['url_frag'] + '/test'
        tmp = _download(url)
        assert tmp == base64.b64decode(f_dae.fragdata.dae)

        # Download and verify the first texture.
        url = base_url + data['test']['url_frag'] + '/rgb1.png'
        tmp = _download(url)
        assert tmp == base64.b64decode(f_dae.fragdata.rgb['rgb1.png'])

        # Download and verify the second texture.
        url = base_url + data['test']['url_frag'] + '/rgb2.jpg'
        tmp = _download(url)
        assert tmp == base64.b64decode(f_dae.fragdata.rgb['rgb2.jpg'])

        # Change the fragment geometries.
        f_raw = getFragRaw()
        cmd = {objID: {'10': f_raw._asdict(), 'test': f_dae._asdict()}}
        assert clerk.setFragments(cmd).ok
        ret = clerk.getFragments([objID])
        assert ret.ok
        data = ret.data[objID]
        del ret

        # Download the 'RAW' file and verify its content is correct.
        url = base_url + data['10']['url_frag'] + '/model.json'
        tmp = _download(url)
        tmp = json.loads(tmp.decode('utf8'))
        assert FragRaw(**tmp) == f_raw.fragdata

        # Download and verify the dae file. Note that the file name itself
        # matches the name of the fragment (ie. 'test'), *not* the name of the
        # original Collada file ('cube.dae').
        url = base_url + data['test']['url_frag'] + '/test'
        tmp = _download(url)
        assert tmp == base64.b64decode(f_dae.fragdata.dae)

        # Download and verify the first texture.
        url = base_url + data['test']['url_frag'] + '/rgb1.png'
        tmp = _download(url)
        assert tmp == base64.b64decode(f_dae.fragdata.rgb['rgb1.png'])

        # Download and verify the second texture.
        url = base_url + data['test']['url_frag'] + '/rgb2.jpg'
        tmp = _download(url)
        assert tmp == base64.b64decode(f_dae.fragdata.rgb['rgb2.jpg'])

        web.terminate()
        web.join()

    def test_updateBoosterValues(self):
        """
        Query and update the booster values in the instance data base.
        The query includes computing the correct force in object coordinates.
        """
        # Convenience.
        clerk = self.clerk

        # ---------------------------------------------------------------------
        # Create a template with two boosters and spawn it. The Boosters are
        # to the left/right of the object and point both in the positive
        # z-direction.
        # ---------------------------------------------------------------------
        boosters = {
            '0': aztypes.Booster(pos=[-1, 0, 0], direction=[0, 0, 1],
                               minval=-1, maxval=1, force=0),
            '1': aztypes.Booster(pos=[+1, 0, 0], direction=[0, 0, 1],
                               minval=-1, maxval=1, force=0)
        }

        # Define a template with one fragment.
        t1 = getTemplate('t1', boosters=boosters)

        # Add the template and spawn two instances.
        assert clerk.addTemplates([t1]).ok
        init = {'templateID': t1.aid}
        ret = clerk.spawn([init, init])
        assert ret.ok
        objID_1, objID_2 = ret.data

        # ---------------------------------------------------------------------
        # Update the Booster forces on the first object: both accelerate the
        # object in z-direction, which means a force purely in z-direction and
        # no torque.
        # ---------------------------------------------------------------------
        cmd_b = {
            '0': aztypes.CmdBooster(force=1),
            '1': aztypes.CmdBooster(force=1),
        }
        ret = clerk.updateBoosterForces(objID_1, cmd_b)
        assert ret.ok
        assert ret.data == ([0, 0, 2], [0, 0, 0])
        del cmd_b, ret

        # ---------------------------------------------------------------------
        # Update the Booster forces on the first object: accelerate the left
        # one upwards and the right one downwards. This must result in a zero
        # net force but non-zero torque.
        # ---------------------------------------------------------------------
        cmd_b = {
            '0': aztypes.CmdBooster(force=1),
            '1': aztypes.CmdBooster(force=-1),
        }
        ret = clerk.updateBoosterForces(objID_1, cmd_b)
        assert ret.ok
        assert ret.data == ([0, 0, 0], [0, 2, 0])
        del cmd_b, ret

        # ---------------------------------------------------------------------
        # Update the Booster forces on the second object to ensure the function
        # correctly distinguishes between objects.
        # ---------------------------------------------------------------------
        # Turn off left Booster of first object (right booster remains active).
        cmd_b = {'0': aztypes.CmdBooster(force=0)}
        ret = clerk.updateBoosterForces(objID_1, cmd_b)
        assert ret.ok
        assert ret.data == ([0, 0, -1], [0, 1, 0])

        # Turn on left Booster of the second object.
        cmd_b = {'0': aztypes.CmdBooster(force=1)}
        ret = clerk.updateBoosterForces(objID_2, cmd_b)
        assert ret.ok
        assert ret.data == ([0, 0, +1], [0, 1, 0])
        del ret, cmd_b

        # ---------------------------------------------------------------------
        # Attempt to update a non-existing Booster or a non-existing object.
        # ---------------------------------------------------------------------
        cmd_b = {'10': aztypes.CmdBooster(force=1)}
        assert not clerk.updateBoosterForces(objID_2, cmd_b).ok

        cmd_b = {'0': aztypes.CmdBooster(force=1)}
        assert not clerk.updateBoosterForces(1000, cmd_b).ok

    def test_add_get_remove_constraints(self):
        """
        Create some bodies. Then add/query/remove constraints.

        This test only verifies that the Igor interface works. It does *not*
        verify that the objects are really linked in the actual simulation.
        """
        clerk = self.clerk

        # Reset the constraint database.
        assert clerk.igor.reset().ok

        # Define three collision shapes.
        pos_1, pos_2, pos_3 = [-2, 0, 0], [2, 0, 0], [6, 0, 0]
        body_1 = getRigidBody(position=pos_1)
        body_2 = getRigidBody(position=pos_2)
        body_3 = getRigidBody(position=pos_3)

        # Spawn the two bodies with a constraint among them.
        tID = '_templateSphere'
        id_1, id_2, id_3 = 1, 2, 3
        init_1 = {
            'templateID': tID,
            'rbs': {
                'position': body_1.position,
            }
        }
        init_2 = {
            'templateID': tID,
            'rbs': {
                'position': body_2.position,
            }
        }
        init_3 = {
            'templateID': tID,
            'rbs': {
                'position': body_3.position,
            }
        }
        ret = clerk.spawn([init_1, init_2, init_3])
        assert (ret.ok, ret.data) == (True, (id_1, id_2, id_3))
        del tID

        # Link the three objects. The first two with a Point2Point constraint
        # and the second two with a 6DofSpring2 constraint.
        con_1 = getP2P(rb_a=id_1, rb_b=id_2, pivot_a=pos_2, pivot_b=pos_1)
        con_2 = get6DofSpring2(rb_a=id_2, rb_b=id_3)

        # Verify that no constraints are currently active.
        assert clerk.getConstraints(None) == (True, None, tuple())
        assert clerk.getConstraints([id_1]) == (True, None, tuple())

        # Add both constraints and verify Clerk returns them correctly.
        assert clerk.addConstraints([con_1, con_2]) == (True, None, 2)
        ret = clerk.getConstraints(None)
        assert ret.ok and (sorted(ret.data) == sorted([con_1, con_2]))

        ret = clerk.getConstraints([id_2])
        assert ret.ok and (sorted(ret.data) == sorted([con_1, con_2]))

        assert clerk.getConstraints([id_1]) == (True, None, (con_1, ))
        assert clerk.getConstraints([id_3]) == (True, None, (con_2, ))

        # Remove one constraint and verify Clerk returns them correctly.
        assert clerk.deleteConstraints([con_2]) == (True, None, 1)
        assert clerk.getConstraints(None) == (True, None, (con_1, ))
        assert clerk.getConstraints([id_1]) == (True, None, (con_1, ))
        assert clerk.getConstraints([id_2]) == (True, None, (con_1,))
        assert clerk.getConstraints([id_3]) == (True, None, tuple())

    def test_constraints_with_physics(self):
        """
        Spawn two rigid bodies and define a Point2Point constraint among them.
        Then apply a force onto one of them and verify the second one moves
        accordingly.
        """
        # Reset the SV database and instantiate a Leonard and a Clerk.
        leo = getLeonard(azrael.leonard.LeonardBullet)
        clerk = self.clerk

        # Reset the constraint database.
        assert clerk.igor.reset().ok

        # Parameters and constants for this test.
        id_a, id_b = 1, 2
        templateID = '_templateSphere'

        # Define two spherical collision shapes at x=+/-2. Since the default
        # sphere is a unit sphere this ensures that the spheres do not touch
        # each other, but have a gap of 2 Meters between them.
        pos_a, pos_b = (-2, 0, 0), (2, 0, 0)
        body_a = getRigidBody(position=pos_a)
        body_b = getRigidBody(position=pos_b)

        # Spawn the two bodies with a constraint among them.
        init_a = {
            'templateID': templateID,
            'rbs': {
                'position': body_a.position,
            }
        }
        init_b = {
            'templateID': templateID,
            'rbs': {
                'position': body_b.position,
            }
        }
        ret = clerk.spawn([init_a, init_b])
        assert (ret.ok, ret.data) == (True, (id_a, id_b))

        # Verify that both objects were spawned (simply query their template
        # ID to establish that).
        ret_a = clerk.getTemplateID(id_a)
        ret_b = clerk.getTemplateID(id_b)
        assert ret_a.ok and ret_b.ok
        assert ret_a.data == ret_b.data == templateID

        # Define the constraints.
        con = [getP2P(rb_a=id_a, rb_b=id_b, pivot_a=pos_b, pivot_b=pos_a)]
        assert clerk.addConstraints(con) == (True, None, 1)

        # Apply a force that will pull the left object further to the left.
        # However, both objects must move the same distance in the same
        # direction because they are now linked together.
        assert clerk.setForce(id_a, [-10, 0, 0], [0, 0, 0]).ok
        leo.processCommandsAndSync()
        leo.step(1.0, 60)
        ret = clerk.getRigidBodies([id_a, id_b])
        assert ret.ok
        pos_a2 = ret.data[id_a]['rbs'].position
        pos_b2 = ret.data[id_b]['rbs'].position
        delta_a = np.array(pos_a2) - np.array(pos_a)
        delta_b = np.array(pos_b2) - np.array(pos_b)
        assert delta_a[0] < pos_a[0]
        assert np.allclose(delta_a, delta_b)

    def test_remove_fragments(self):
        """
        Remove a fragment.
        """
        clerk = self.clerk

        # The original template has the following three fragments:
        frags_orig = {
            'fname_1': getFragRaw(),
            'fname_2': getFragDae(),
            'fname_3': getFragRaw()
        }
        t1 = getTemplate('t1', fragments=frags_orig)

        # Add a new template, spawn it, and record the object ID.
        assert clerk.addTemplates([t1]).ok
        ret = clerk.spawn([{'templateID': 't1'}])
        assert ret.ok
        objID = ret.data[0]

        # Query the fragment geometries and body state to verify that both
        # report three fragments.
        ret = clerk.getFragments([objID])
        assert ret.ok and len(ret.data[objID]) == 3
        ret = clerk.getObjectStates([objID])
        assert ret.ok and len(ret.data[objID]['frag']) == 3

        # Update the fragments as follows: keep the first intact, remove the
        # second, and modify the third one.
        cmd = {objID: {'fname_2': getFragNone()._asdict(),
                       'fname_3': getFragDae()._asdict()}}
        assert clerk.setFragments(cmd).ok

        # After the last update only two fragments must remain.
        ret = clerk.getFragments([objID])
        assert ret.ok and len(ret.data[objID]) == 2
        ret = clerk.getObjectStates([objID])
        assert ret.ok and len(ret.data[objID]['frag']) == 2

    def test_setRigidBodies(self):
        """
        Spawn an object and update its body attributes.
        """
        clerk = self.clerk

        # Constants and parameters for this test.
        id_1, id_2 = 1, 2

        # Spawn one of the default templates.
        init = {'templateID': '_templateSphere',
                'rbs': {'position': [0, 0, 0], 'velocityLin': [-1, -2, -3]}}
        ret = clerk.spawn([init, init])
        assert ret.ok and (ret.data == (id_1, id_2))

        # Verify that the initial body states are correct.
        ret = clerk.getRigidBodies([id_1, id_2])
        assert ret.ok
        ret_1 = ret.data[id_1]['rbs']
        ret_2 = ret.data[id_2]['rbs']
        assert isinstance(ret_1, aztypes._RigidBodyData)
        assert ret_1.position == init['rbs']['position']
        assert ret_1.velocityLin == init['rbs']['velocityLin']
        assert ret_2.position == init['rbs']['position']
        assert ret_2.velocityLin == init['rbs']['velocityLin']

        # Selectively update the body parameters for id_1.
        new_bs = {
            'position': [1, -1, 1],
            'imass': 2,
            'scale': 3,
            'cshapes': {'cssphere': getCSBox()._asdict()}}
        assert clerk.setRigidBodies({id_1: new_bs}).ok

        # Verify that the specified attributes for id_1 have changed, but the
        # other ones (in particular velocityLin because we overwrote it in the
        # spawn command) remained unaffected.
        ret = clerk.getRigidBodies([id_1, id_2])
        assert ret.ok
        ret_1 = ret.data[id_1]['rbs']
        ret_2 = ret.data[id_2]['rbs']
        assert isinstance(ret_1, aztypes._RigidBodyData)
        assert ret_1.imass == new_bs['imass']
        assert ret_1.scale == new_bs['scale']
        assert ret_1.position == new_bs['position']
        assert ret_1.velocityLin == init['rbs']['velocityLin']

        # Object id_2 must not have changed at all.
        assert ret_2.imass == 1
        assert ret_2.scale == 1
        assert ret_2.position == init['rbs']['position']
        assert CollShapeMeta(**ret_1.cshapes['cssphere']) == getCSBox()
        assert CollShapeMeta(**ret_2.cshapes['cssphere']) == getCSSphere()

        # Attempt to update an unknown attribute.
        new_bs_2 = {
            'blah': [1, -1, 1],
            'imass': 2,
            'scale': 3,
            'cshapes': {'cssphere': getCSSphere()._asdict()}}
        assert not clerk.setRigidBodies({id_1: new_bs_2}).ok

        # Attempt to update one valid and one invalid object. This must update
        # the valid object only.
        new_bs_3 = {
            'position': [2, -2, 2],
            'imass': 3,
            'scale': 4,
            'cshapes': {'cssphere': getCSPlane()._asdict()}}
        ret = clerk.setRigidBodies({id_2: new_bs_3, 10: new_bs_3})
        assert ret == (True, None, [10])

        # Verify that id_1 has the new attributes and id_2 remained unaffected.
        ret = clerk.getRigidBodies([id_1, id_2])
        assert ret.ok
        ret_1 = ret.data[id_1]['rbs']
        ret_2 = ret.data[id_2]['rbs']
        assert isinstance(ret_1, aztypes._RigidBodyData)
        assert ret_1.imass == new_bs['imass']
        assert ret_1.scale == new_bs['scale']
        assert ret_1.position == new_bs['position']
        assert ret_2.imass == new_bs_3['imass']
        assert ret_2.scale == new_bs_3['scale']
        assert ret_2.position == new_bs_3['position']
        assert CollShapeMeta(**ret_1.cshapes['cssphere']) == getCSBox()
        assert CollShapeMeta(**ret_2.cshapes['cssphere']) == getCSPlane()

    def test_stunted_objects(self):
        """
        I define a "stunted" object as one that lacks collision shapes,
        or fragments, or both. Whereas most bodies usually have both there
        exist cases where "stunted" objects are useful. For instance, to
        cause a collision with an invisible object, or draw an object that does
        not collide with anything.

        This test creates the three test cases and verifies that
        `Clerk.getRigidBodies' handles them correctly.
        """
        # Create a Leonard and Clerk.
        leo = getLeonard(azrael.leonard.LeonardBullet)
        clerk = self.clerk

        # Create templates for all possible "stunted" objects.
        body_cs = getRigidBody(cshapes={'cssphere': getCSSphere()})
        body_nocs = getRigidBody(cshapes={})
        t_cs = getTemplate('t_cs', rbs=body_cs, fragments={})
        t_frag = getTemplate('t_frag', rbs=body_nocs, fragments={'foo': getFragRaw()})
        t_none = getTemplate('t_none', rbs=body_nocs, fragments={})

        # Add the templates to Azrael and verify it accepted them.
        assert clerk.addTemplates([t_cs, t_frag, t_none]).ok

        # Spawn an instance of each.
        ret = clerk.spawn([{'templateID': 't_cs'},
                           {'templateID': 't_frag'},
                           {'templateID': 't_none'}])
        assert ret.ok
        id_cs, id_frag, id_none = ret.data

        # Verify that Leonard does not complain about the two objects without
        # collision shape.
        leo.processCommandsAndSync()

        # Modify the position of all three objects.
        new_bs_cs = {'position': [0, 1, 2]}
        new_bs_frag = {'position': [3, 4, 5]}
        new_bs_none = {'position': [6, 7, 8]}

        cmd = {
            id_cs: new_bs_cs,
            id_frag: new_bs_frag,
            id_none: new_bs_none,
        }
        assert clerk.setRigidBodies(cmd).ok

        # Verify that all bodies are at their new positions.
        ret_os = clerk.getObjectStates([id_cs, id_frag, id_none])
        ret_rb = clerk.getRigidBodies([id_cs, id_frag, id_none])
        assert ret_os.ok and ret_rb.ok

        r_os = ret_os.data
        r_rb = ret_rb.data
        assert len(r_os[id_frag]['frag']) == 1
        assert r_rb[id_frag]['rbs'].position == new_bs_frag['position']
        assert r_os[id_cs]['frag'] == {}
        assert r_rb[id_cs]['rbs'].position == new_bs_cs['position']
        assert r_os[id_none]['frag'] == {}
        assert r_rb[id_none]['rbs'].position == new_bs_none['position']

    def test_set_get_custom(self):
        """
        Spawn an object and modify its custom data.
        """
        # Convenience.
        clerk = self.clerk
        id_1, id_2 = 1, 2
        init = {'templateID': '_templateSphere'}
        ret = clerk.spawn([init, init])
        assert ret == (True, None, (id_1, id_2))

        # Query the custom data for a non-existing object.
        assert clerk.getCustomData([10]) == (True, None, {10: None})

        # Query an existing object.
        assert clerk.getCustomData([id_1]) == (True, None, {id_1: ''})

        # Set the custom data for a non-existing object.
        assert clerk.setCustomData({10: 'blah'}) == (True, None, [10])

        # Set/get the custom data for an existing object.
        ret = clerk.setCustomData({id_1: 'foo', 20: 'bar'})
        assert ret.data == [20]
        ret = clerk.getCustomData([id_1, id_2])
        assert ret == (True, None, {id_1: 'foo', id_2: ''})

        # Get all 'custom' fields at once.
        assert clerk.getCustomData([id_1, id_2]) == clerk.getCustomData(None)

        # Attempt to store something other than a string.
        assert clerk.getCustomData([id_1]) == (True, None, {id_1: 'foo'})
        assert clerk.setCustomData({id_1: 10}) == (True, None, [id_1])
        assert clerk.getCustomData([id_1]) == (True, None, {id_1: 'foo'})

        # Attempt to use a string that exceeds the 16k limit.
        max_len = 2 ** 16
        long_string = 'v' * max_len
        short_string = 'i' * (max_len - 1)
        assert clerk.getCustomData([id_1]) == (True, None, {id_1: 'foo'})
        assert clerk.setCustomData({id_1: long_string}) == (True, None, [id_1])
        assert clerk.getCustomData([id_1]) == (True, None, {id_1: 'foo'})
        assert clerk.setCustomData({id_1: short_string}).ok
        assert clerk.getCustomData([id_1]) == (True, None, {id_1: short_string})

    def test_remove_sync_bug(self):
        """
        Leonard (accidentally) used an upsert query instead of an update query.
        This may lead to Leonard partially updating a record in the master that
        does not exist (anymore), most likely because the object was deleted
        during the physics cycle.

        I could not think of an elegant way to test this via a Clerk method
        since those method can deal with corrupt data. The test therefore
        queries Mongo directly - not ideal due to its database dependency, but
        at least it is a solid test.

        Note that this test should become redundant once Clerk gains a method
        to update rigid body states, whereas right now Leonard writes to the
        database directly (legacy architecture).
        """
        # Create a Leonard and Clerk.
        leo = getLeonard(azrael.leonard.LeonardBullet)
        clerk = self.clerk

        # Convenience.
        id_1 = 1
        body_1 = getRigidBody(imass=1)
        db = azrael.database.dbHandles['ObjInstances']

        # Database and Leonard cache must both be empty.
        assert db.count() == 0
        assert len(leo.allBodies) == len(leo.allForces) == 0

        # Announce a newly spawned object in a way that bypasses Clerk. This
        # will ensure that Clerk does not add anything to the master record.
        import azrael.leo_api as leoAPI
        assert leoAPI.addCmdSpawn([(id_1, body_1)]).ok
        leo.processCommandsAndSync()

        # Verify that Leonard now holds exactly one object.
        assert len(leo.allBodies) == len(leo.allForces) == 1

        # Verify further that Leonard did *not* create an entry in the master
        # record due to an errornous 'upsert' command.
        assert db.count() == 0


def test_invalid():
    """
    Send invalid commands to Clerk. Use the actual ZeroMQ link.
    """
    class ClerkConnector():
        """
        Test class to connect to Clerk via ZeroMQ.
        """
        def __init__(self):
            # Convenience.
            ip = config.addr_clerk
            port = config.port_clerk

            # Create ZeroMQ sockets and connect them to Clerk.
            self.ctx = zmq.Context()
            self.sock_cmd = self.ctx.socket(zmq.REQ)
            self.sock_cmd.linger = 0
            self.sock_cmd.connect('tcp://{}:{}'.format(ip, port))

        def __del__(self):
            self.sock_cmd.close(linger=0)
            self.ctx.destroy()

        def testSend(self, data):
            """
            Pass data verbatim to Clerk.
            """
            self.sock_cmd.send(data)
            data = self.sock_cmd.recv()
            return RetVal(**json.loads(data.decode('utf8')))

    # Start Clerk and instantiate a Client.
    killAzrael()
    clerk = azrael.clerk.Clerk()
    clerk.start()
    client = ClerkConnector()

    # Send a corrupt JSON to Clerk.
    msg = 'this is not a json string'
    ret = client.testSend(msg.encode('utf8'))
    assert ret == (False, 'JSON decoding error in Clerk', None)

    # Send a malformatted JSON (it misses the mandatory 'data' field).
    msg = json.dumps({'cmd': 'blah'})
    ret = client.testSend(msg.encode('utf8'))
    assert ret == (False, 'Invalid command format', None)

    # Send an invalid command.
    msg = json.dumps({'cmd': 'blah', 'data': ''})
    ret = client.testSend(msg.encode('utf8'))
    assert ret == (False, 'Invalid command <blah>', None)

    # Correct command but 'data' is not a dictionary.
    msg = json.dumps({'cmd': 'get_rigid_bodies', 'data': [1, 2]})
    assert not client.testSend(msg.encode('utf8')).ok

    # Correct command and payload type, correct 'data' type, but the keys do
    # not match the signature of 'Clerk.getTemplates'.
    data = {'blah': [1, 2]}
    msg = json.dumps({'cmd': 'get_rigid_bodies', 'data': data})
    assert not client.testSend(msg.encode('utf8')).ok

    # Correct command, correct payload type, correct payload content. This must
    # succeed.
    data = {'objIDs': [1, 2]}
    msg = json.dumps({'cmd': 'get_rigid_bodies', 'data': data})
    assert client.testSend(msg.encode('utf8')).ok

    # Terminate the Clerk.
    clerk.terminate()
    clerk.join()
