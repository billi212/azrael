# Copyright 2014, Oliver Nagy <olitheolix@gmail.com>
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
The encoders and decoders in this module specify the binary protocol for
sending/receiving messages to/from Clerk.

``ToClerk_*_Decode``: Clerk will use this function to de-serialise the incoming
byte stream into native Python types.

``FromClerk_*_Encode``: Clerk will use this function to serialise its response.

``ToClerk_*_Encode``: the (Python) client uses this function to serialise its
request for Clerk.

``FromClerk_*_Decode``: the (Python) client uses this function to de-serialise
Clerk's response.

The binary protocols are not pickled Python objects but (hopefully) language
agnostic encodings of strings, JSON objects, or C-arrays (via NumPy). This
should make it possible to write clients in other languages.
"""

import json
import cytoolz
import collections
import numpy as np
import azrael.parts as parts
import azrael.config as config
import azrael.bullet.btInterface as btInterface
from azrael.typecheck import typecheck


class AzraelEncoder(json.JSONEncoder):
    """
    Augment default JSON encoder to handle bytes and NumPy arrays.
    """
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, bytes):
            return list(obj)
        if isinstance(obj, np.int64):
            return int(obj)
        if isinstance(obj, np.float64):
            return float(obj)
        return json.JSONEncoder.default(self, obj)

def dumps(data):
    # Convenience function for encoding ``data`` with custom JSON encoder.
    return json.dumps(data, cls=AzraelEncoder)

def loads(data: bytes):
    # Convenience function for decoding ``data``.
    return json.loads(data.decode('utf8'))

# ---------------------------------------------------------------------------
# GetTemplate
# ---------------------------------------------------------------------------

@typecheck
def ToClerk_GetTemplate_Encode(templateID: bytes):
    return True, templateID


@typecheck
def ToClerk_GetTemplate_Decode(payload: bytes):
    return True, (payload, )


@typecheck
def FromClerk_GetTemplate_Encode(cs: np.ndarray, geo: np.ndarray,
                                 boosters: (list, tuple),
                                 factories: (list, tuple)):
    d = {'cs': cs, 'geo': geo, 'boosters': boosters,
         'factories': factories}
    return True, dumps(d).encode('utf8')


@typecheck
def FromClerk_GetTemplate_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    # Wrap the Booster- and Factory data into their dedicated named tuples.
    boosters = [parts.booster(*_) for _ in data['boosters']]
    factories = [parts.factory(*_) for _ in data['factories']]

    # Return the complete information in a named tuple.
    nt = collections.namedtuple('Template', 'cs geo boosters factories')
    ret = nt(np.array(data['cs'], np.float64),
             np.array(data['geo'], np.float64),
             boosters, factories)
    return True, ret


# ---------------------------------------------------------------------------
# GetTemplateID
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_GetTemplateID_Encode(objID: bytes):
    return True, objID


@typecheck
def ToClerk_GetTemplateID_Decode(payload: bytes):
    return True, (payload, )


@typecheck
def FromClerk_GetTemplateID_Encode(templateID: bytes):
    return True, templateID


@typecheck
def FromClerk_GetTemplateID_Decode(payload: bytes):
    return True, payload


# ---------------------------------------------------------------------------
# AddTemplate
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_AddTemplate_Encode(templateID: bytes, cs: np.ndarray, geo:
                               np.ndarray, boosters, factories):
    d = {'name': templateID, 'cs': cs.tostring(), 'geo': geo.tostring(),
         'boosters': boosters, 'factories': factories}
    try:
        d = dumps(d).encode('utf8')
    except TypeError:
        return False, 'JSON encoding error'
    return True, d


@typecheck
def ToClerk_AddTemplate_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    # Wrap the Booster- and Factory data into their dedicated named tuples.
    boosters = [parts.booster(*_) for _ in data['boosters']]
    factories = [parts.factory(*_) for _ in data['factories']]

    # Convert template ID to a byte string.
    templateID = bytes(data['name'])

    # Convert collision shape and geometry to NumPy array (via byte string).
    cs = np.fromstring(bytes(data['cs']), np.float64)
    geo = np.fromstring(bytes(data['geo']), np.float64)

    # Return decoded quantities.
    return True, (templateID, cs, geo, boosters, factories)


@typecheck
def FromClerk_AddTemplate_Encode(templateID: bytes):
    return True, templateID


@typecheck
def FromClerk_AddTemplate_Decode(payload: bytes):
    return True, payload


# ---------------------------------------------------------------------------
# GetAllObjectIDs
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_GetAllObjectIDs_Encode(dummyarg=None):
    return True, b''


@typecheck
def ToClerk_GetAllObjectIDs_Decode(payload: bytes):
    return True, b''


@typecheck
def FromClerk_GetAllObjectIDs_Encode(data: (list, tuple)):
    # Join all object IDs into a single byte stream.
    data = b''.join(data)
    return True, data


@typecheck
def FromClerk_GetAllObjectIDs_Decode(payload: bytes):
    # Partition the byte stream into individual object IDs.
    data = [bytes(_) for _ in cytoolz.partition(config.LEN_ID, payload)]
    return True, data


# ---------------------------------------------------------------------------
# SuggestPosition
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_SuggestPosition_Encode(objID: bytes, pos: np.ndarray):
    d = {'objID': objID, 'pos': pos}

    # Encode data as JSON.
    try:
        d = dumps(d).encode('utf8')
    except TypeError:
        return False, 'JSON encoding error'
    return True, d


@typecheck
def ToClerk_SuggestPosition_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    # Convert to native Python types and return to caller.
    objID = bytes(data['objID'])
    pos = np.array(data['pos'], np.float64)
    return True, (objID, pos)


@typecheck
def FromClerk_SuggestPosition_Encode(ret):
    return True, ret.encode('utf8')


@typecheck
def FromClerk_SuggestPosition_Decode(payload: bytes):
    return True, payload


# ---------------------------------------------------------------------------
# SetForce
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_SetForce_Encode(objID: bytes, force: np.ndarray, rel_pos: np.ndarray):
    d = {'objID': objID, 'rel_pos': rel_pos, 'force': force}

    # Encode data as JSON.
    try:
        d = dumps(d).encode('utf8')
    except TypeError:
        return False, 'JSON encoding error'
    return True, d


@typecheck
def ToClerk_SetForce_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    # Convert to native Python types and return to caller.
    objID = bytes(data['objID'])
    force = np.array(data['force'], np.float64)
    rel_pos = np.array(data['rel_pos'], np.float64)
    return True, (objID, force, rel_pos)


@typecheck
def FromClerk_SetForce_Encode(ret):
    return True, ret.encode('utf8')


@typecheck
def FromClerk_SetForce_Decode(payload: bytes):
    return True, payload


# ---------------------------------------------------------------------------
# GetGeometry
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_GetGeometry_Encode(target: bytes):
    return True, target


@typecheck
def ToClerk_GetGeometry_Decode(payload: bytes):
    return True, (payload, )


@typecheck
def FromClerk_GetGeometry_Encode(geo: np.ndarray):
    return True, geo.tostring()


@typecheck
def FromClerk_GetGeometry_Decode(payload: bytes):
    return True, np.fromstring(payload)


# ---------------------------------------------------------------------------
# GetStateVariables
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_GetStateVariable_Encode(objIDs: (tuple, list)):
    return True, b''.join(objIDs)


@typecheck
def ToClerk_GetStateVariable_Decode(payload: bytes):
    # We need at least one ID.
    if len(payload) < config.LEN_ID:
        return False, 'Insufficient arguments'

    # The byte string must be an integer multiple of the object ID.
    if (len(payload) % config.LEN_ID) != 0:
        return False, 'Not divisible by objID length'

    # Turn the byte string into a list of object IDs.
    objIDs = [bytes(_) for _ in cytoolz.partition(config.LEN_ID, payload)]

    # Return the result.
    return True, (objIDs, )


@typecheck
def FromClerk_GetStateVariable_Encode(objIDs: (list, tuple),
                                      sv: (list, tuple)):
    data = [_[0] + _[1] for _ in zip(objIDs, sv)]
    return True, b''.join(data)


@typecheck
def FromClerk_GetStateVariable_Decode(payload: bytes):
    # The available data must be an integer multiple of an ID plus SV.
    l = config.LEN_ID + config.LEN_SV_BYTES
    assert (len(payload) % l) == 0

    # Return a dictionary of SV variables. The dictionary key is the
    # object ID (the state variables - incidentally - are another
    # dictionary).
    out = {}
    for data in cytoolz.partition(l, payload):
        data = bytes(data)
        sv = np.fromstring(data[config.LEN_ID:])
        out[data[:config.LEN_ID]] = btInterface.unpack(sv)
    return True, out


# ---------------------------------------------------------------------------
# Spawn
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_Spawn_Encode(name: bytes, templateID: bytes, sv:
                         btInterface.BulletData):
    sv = btInterface.pack(sv).tostring()
    d = {'name': name, 'templateID': templateID, 'sv': sv}
    return True, dumps(d).encode('utf8')


@typecheck
def ToClerk_Spawn_Decode(payload: bytes):
    data = loads(payload)
    if data['name'] is None:
        ctrl_name = None
    else:
        ctrl_name = bytes(data['name'])
    templateID = bytes(data['templateID'])
    sv = np.fromstring(bytes(data['sv']), np.float64)
    sv = btInterface.unpack(sv)

    if sv is None:
        return False, 'Invalid State Variable data'
    else:
        return True, (ctrl_name, templateID, sv)


@typecheck
def FromClerk_Spawn_Encode(objID: bytes):
    return True, objID


@typecheck
def FromClerk_Spawn_Decode(payload: bytes):
    return True, payload


# ---------------------------------------------------------------------------
# RecvMsg
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_RecvMsg_Encode(objID: bytes):
    return True, objID


@typecheck
def ToClerk_RecvMsg_Decode(payload: bytes):
    # Check if any messages for a particular controller ID are
    # pending. Return the first such message if there are any and
    # remove them from the queue. The controller ID is the only
    # payload.
    obj_id = payload[:config.LEN_ID]

    if len(obj_id) != config.LEN_ID:
        return False, 'Insufficient arguments'
    else:
        return True, (obj_id, )

@typecheck
def FromClerk_RecvMsg_Encode(objID: bytes, msg: bytes):
    d = {'objID': objID, 'msg': msg}
    # Encode data as JSON.
    try:
        d = dumps(d).encode('utf8')
    except TypeError:
        return False, 'JSON encoding error'
    return True, d


@typecheck
def FromClerk_RecvMsg_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    # Unpack the message source. If this string is invalid (most likely empty)
    # then it means no message was available for us.
    src = bytes(data['objID'])
    if len(src) < config.LEN_ID:
        return True, (None, b'')
    else:
        msg = bytes(data['msg'])
        return True, (src, msg)


# ---------------------------------------------------------------------------
# SendMsg
# ---------------------------------------------------------------------------

@typecheck
def ToClerk_SendMsg_Encode(objID: bytes, target: bytes, msg: bytes):
    d = {'src': objID, 'dst': target, 'msg': msg}
    # Encode data as JSON.
    try:
        d = dumps(d).encode('utf8')
    except TypeError:
        return False, 'JSON encoding error'
    return True, d


@typecheck
def ToClerk_SendMsg_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    src = bytes(data['src'])
    dst = bytes(data['dst'])
    msg = bytes(data['msg'])

    if len(dst) != config.LEN_ID:
        return False, 'Insufficient arguments'
    else:
        return True, (src, dst, msg)


@typecheck
def FromClerk_SendMsg_Encode(dummyarg=None):
    return True, b''


@typecheck
def FromClerk_SendMsg_Decode(payload: bytes):
    return True, tuple()


# ---------------------------------------------------------------------------
# ControlParts
# ---------------------------------------------------------------------------


@typecheck
def ToClerk_ControlParts_Encode(objID: bytes, cmds_b: list, cmds_f: list):
    # Sanity checks.
    for cmd in cmds_b:
        assert isinstance(cmd, parts.CmdBooster)
    for cmd in cmds_f:
        assert isinstance(cmd, parts.CmdFactory)

    # Every object can have at most 256 parts.
    assert len(cmds_b) < 256
    assert len(cmds_f) < 256

    d = {'objID': objID, 'cmd_boosters': cmds_b, 'cmd_factories': cmds_f}
    # Encode data as JSON.
    try:
        d = dumps(d).encode('utf8')
    except TypeError:
        return False, 'JSON encoding error'
    return True, d


@typecheck
def ToClerk_ControlParts_Decode(payload: bytes):
    # Decode JSON.
    try:
        data = loads(payload)
    except ValueError:
        return False, 'JSON decoding error'

    objID = bytes(data['objID'])
    cmds_b = [parts.CmdBooster(*_) for _ in data['cmd_boosters']]
    cmds_f = [parts.CmdFactory(*_) for _ in data['cmd_factories']]
        
    return True, (objID, cmds_b, cmds_f)


@typecheck
def FromClerk_ControlParts_Encode(dummyarg=None):
    return True, b''


@typecheck
def FromClerk_ControlParts_Decode(payload: bytes):
    return True, tuple()
