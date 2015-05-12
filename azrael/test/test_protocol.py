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
import json
import base64
import pytest
import numpy as np

import azrael.parts as parts
import azrael.config as config
import azrael.protocol as protocol
import azrael.physics_interface as physAPI
import azrael.bullet_data as bullet_data

from IPython import embed as ipshell
from azrael.test.test_bullet_api import isEqualBD
from azrael.types import FragState, FragDae, FragRaw, MetaFragment, Template


def test_encoding_get_template(clientType='ZeroMQ'):
    """
    Test codec for {add,get}Template functions.
    """
    # Test parameters and constants.
    template_name = 'mytemplate'
    b0 = parts.Booster(partID='0', pos=np.zeros(3), direction=[0, 0, 1],
                       minval=0, maxval=0.5, force=0)
    b1 = parts.Booster(partID='1', pos=np.zeros(3), direction=[1, 1, 0],
                       minval=0, maxval=0.6, force=0)
    f0 = parts.Factory(
        partID='0', pos=np.zeros(3), direction=[0, 0, 1],
        templateID='_templateCube', exit_speed=[0.1, 0.5])

    # ----------------------------------------------------------------------
    # Client --> Clerk.
    # ----------------------------------------------------------------------
    # Encode source data.
    ret = protocol.ToClerk_GetTemplates_Encode([template_name])

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(ret.data))

    # Decode the data.
    ok, dec = protocol.ToClerk_GetTemplates_Decode(enc)
    assert dec[0] == [template_name]

    # ----------------------------------------------------------------------
    # Clerk --> Client.
    # ----------------------------------------------------------------------
    # Encode source data.
    cs = [1, 2, 3, 4]
    data = {'cshape': cs, 'boosters': [b0, b1], 'factories': [f0],
            'aabb': 1.0, 'url': 'http://somewhere',
            'fragments': MetaFragment('foo', 'raw', None)}
    templates = {template_name: data}
    ok, enc = protocol.FromClerk_GetTemplates_Encode(templates)

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(enc))

    # Decode the data.
    dec = protocol.FromClerk_GetTemplates_Decode(enc)

    # Verify.
    assert dec.ok
    dec = dec.data[template_name]
    assert np.array_equal(dec.cs, cs)
    assert len(dec.boosters) == 2
    assert len(dec.factories) == 1

    print('Test passed')


def test_send_command():
    """
    Test controlParts codec.
    """
    # Define the commands.
    cmd_0 = parts.CmdBooster(partID='0', force=0.2)
    cmd_1 = parts.CmdBooster(partID='1', force=0.4)
    cmd_2 = parts.CmdFactory(partID='0', exit_speed=0)
    cmd_3 = parts.CmdFactory(partID='2', exit_speed=0.4)
    cmd_4 = parts.CmdFactory(partID='3', exit_speed=4)
    objID = 1

    # ----------------------------------------------------------------------
    # Client --> Clerk.
    # ----------------------------------------------------------------------

    # Convenience.
    enc_fun = protocol.ToClerk_ControlParts_Encode
    dec_fun = protocol.ToClerk_ControlParts_Decode

    # Encode the booster- and factory commands.
    ret = enc_fun(objID, [cmd_0, cmd_1], [cmd_2, cmd_3, cmd_4])
    assert ret.ok

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(ret.data))

    # Decode the data and verify the correct number of commands was returned.
    ok, (dec_objID, dec_booster, dec_factory) = dec_fun(enc)
    assert (ok, dec_objID) == (True, objID)
    assert len(dec_booster) == 2
    assert len(dec_factory) == 3

    # Use getattr to automatically test all attributes.
    assert dec_booster[0] == cmd_0
    assert dec_booster[1] == cmd_1
    assert dec_factory[0] == cmd_2
    assert dec_factory[1] == cmd_3
    assert dec_factory[2] == cmd_4

    # ----------------------------------------------------------------------
    # Clerk --> Client
    # ----------------------------------------------------------------------

    # Convenience.
    enc_fun = protocol.FromClerk_ControlParts_Encode
    dec_fun = protocol.FromClerk_ControlParts_Decode
    objIDs = [1, 2]

    # Encode source data.
    ok, enc = enc_fun(objIDs)
    assert ok

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(enc))

    # Decode the data.
    ret = dec_fun(enc)
    assert (ret.ok, ret.data) == (True, objIDs)

    print('Test passed')


def test_GetStateVariable():
    """
    Test codec for MotionState tuple.
    """
    objs = [{'frag': {}, 'sv': bullet_data.MotionState()},
            {'frag': {}, 'sv': bullet_data.MotionState()}]
    objIDs = [1, 2]

    # ----------------------------------------------------------------------
    # Client --> Clerk.
    # ----------------------------------------------------------------------
    # Encode source data.
    ret = protocol.ToClerk_GetStateVariable_Encode(objIDs)
    assert ret.ok

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(ret.data))

    # Decode the data.
    ok, (dec_ids, ) = protocol.ToClerk_GetStateVariable_Decode(enc)
    assert (ok, len(dec_ids)) == (True, 2)

    # Verify.
    assert dec_ids == objIDs

    # ----------------------------------------------------------------------
    # Clerk --> Client.
    # ----------------------------------------------------------------------
    # Encode source data.
    data = dict(zip(objIDs, objs))
    ok, enc = protocol.FromClerk_GetStateVariable_Encode(data)

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(enc))

    # Decode the data.
    dec_sv = protocol.FromClerk_GetStateVariable_Decode(enc)
    assert (dec_sv.ok, len(dec_sv.data)) == (True, 2)

    # Verify.
    dec_sv = dec_sv.data
    dec_sv = {int(_): bullet_data._MotionState(**dec_sv[_]['sv'])
              for _ in dec_sv}
    assert isEqualBD(dec_sv[1], objs[0]['sv'])
    assert isEqualBD(dec_sv[2], objs[1]['sv'])

    print('Test passed')


def test_addTemplate_collada(clientType='ZeroMQ'):
    """
    Test addTemplate codec with Collada data.
    """
    # Collada format: a .dae file plus a list of textures in jpg or png format.
    dae_file = b'abc'
    dae_rgb1 = b'def'
    dae_rgb2 = b'ghj'

    # Encode the data as Base64.
    b64e = base64.b64encode
    b64_dae_file = b64e(dae_file).decode('utf8')
    b64_dae_rgb1 = b64e(dae_rgb1).decode('utf8')
    b64_dae_rgb2 = b64e(dae_rgb2).decode('utf8')

    # Compile the Collada fragment with the Base64 encoded data.
    f_dae = FragDae(dae=dae_file,
                    rgb={'rgb1.png': dae_rgb1,
                         'rgb2.jpg': dae_rgb2})

    # Same, but all entries are Base64 encoded.
    b64_f_dae = FragDae(dae=b64_dae_file,
                        rgb={'rgb1.png': b64_dae_rgb1,
                             'rgb2.jpg': b64_dae_rgb2})

    # Compile a valid Template structure.
    frags = [MetaFragment('f_dae', 'dae', b64_f_dae)]
    temp = Template('foo', [4, 1, 1, 1], frags, [], [])

    # ----------------------------------------------------------------------
    # Client --> Clerk.
    # ----------------------------------------------------------------------
    # Encode source data.
    ret = protocol.ToClerk_AddTemplates_Encode([temp])
    assert ret.ok

    # Convert output to JSON and back (simulates the wire transmission).
    enc = json.loads(json.dumps(ret.data))

    # Decode the data.
    ok, dec = protocol.ToClerk_AddTemplates_Decode(enc)

    # Extract the data from the first fragment of the first template.
    dec_frag = dec[0][0].fragments[0].data

    # Compare with the Fragment before it was Base64 encoded.
    assert dec_frag == f_dae

    print('Test passed')


if __name__ == '__main__':
    test_GetStateVariable()
    test_send_command()
    test_encoding_get_template()
    test_addTemplate_collada()
