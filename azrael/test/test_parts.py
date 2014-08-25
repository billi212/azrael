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

import numpy as np
import azrael.parts as parts


def test_booster():
    """
    Test (de)serialisation of Booster tuple.
    """
    # Serialise a Booster tuple.
    orig = parts.booster(1)
    a = parts.booster_tostring(orig)
    assert isinstance(a, bytes)

    # De-serialise it again and compare to the original.
    new = parts.booster_fromstring(a)
    for ii in range(len(orig)):
        assert np.array_equal(orig[ii], new[ii])

    print('Test passed')


def test_factory():
    """
    Test (de)serialisation of Booster tuple.
    """
    # Serialise a Factory tuple.
    orig = parts.factory(1)
    a = parts.factory_tostring(orig)
    assert isinstance(a, bytes)

    # De-serialise it again and compare to the original.
    new = parts.factory_fromstring(a)
    for ii in range(len(orig)):
        assert np.array_equal(orig[ii], new[ii])

    print('Test passed')


if __name__ == '__main__':
    test_booster()
    test_factory()
