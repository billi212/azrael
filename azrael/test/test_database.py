"""
Todo: tests for
  - invalid arguments to any of the methods
  - put:
     * verify return values for different combinations of exist
     * repeat, but use multiple objects and check the boolean return dict
  - put/mod must verify that none of the keys contains a dot ('.').
  - setInc
  - several corner cases for when a variable to increment does not exist, or if
    it does exist but has the wrong type.
  - rename 'objID' to 'aid' in Mongo driver (only after all of Azrael uses it)
"""
import pytest
import azrael.database as database

from IPython import embed as ipshell


class TestAtomicCounter:
    @classmethod
    def setup_class(cls):
        pass

    @classmethod
    def teardown_class(cls):
        pass

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def test_increment_WPCounter(self):
        """
        Reset the Counter DB and fetch a few counter values.
        """
        # Reset Azrael.
        database.init()
        ret = database.getUniqueObjectIDs(0)
        assert ret.ok and ret.data == 0

        ret = database.getUniqueObjectIDs(1)
        assert ret.ok and ret.data == (1, )

        # Ask for new counter values.
        for ii in range(5):
            ret = database.getUniqueObjectIDs(1)
            assert ret.ok
            assert ret.data == (ii + 2, )

        # Reset Azrael again and verify that all counters start at '1' again.
        database.init()
        ret = database.getUniqueObjectIDs(0)
        assert ret.ok and ret.data == 0

        ret = database.getUniqueObjectIDs(3)
        assert ret.ok
        assert ret.data == (1, 2, 3)

        # Increment the counter by a different values.
        database.init()
        ret = database.getUniqueObjectIDs(0)
        assert ret.ok and ret.data == 0

        ret = database.getUniqueObjectIDs(2)
        assert ret.ok and ret.data == (1, 2)

        ret = database.getUniqueObjectIDs(3)
        assert ret.ok and ret.data == (3, 4, 5)

        ret = database.getUniqueObjectIDs(4)
        assert ret.ok and ret.data == (6, 7, 8, 9)

        # Run invalid queries.
        assert not database.getUniqueObjectIDs(-1).ok


allEngines = [
    database.DatabaseInMemory,
    database.DatabaseMongo,
]

class TestDatabaseAPI:
    @classmethod
    def setup_class(cls):
        pass

    @classmethod
    def teardown_class(cls):
        pass

    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    @pytest.mark.parametrize('clsDatabase', allEngines)
    def test_reset_add(self, clsDatabase):
        """
        Add data and verify that 'reset' flushes it.
        """
        db = clsDatabase(name=('test1', 'test2'))

        # Reset the database and verify that it is empty.
        assert db.reset().ok
        assert db.count() == (True, None, 0)

        # Insert one document and verify the document count is now at 1.
        ops = {'1': {'exists': False, 'data': {'key': 'value'}}}
        assert db.put(ops) == (True, None, {'1': True})
        assert db.count() == (True, None, 1)
            
        # Reset the database and verfify that it is empty again.
        assert db.reset() == (True, None, None)
        assert db.count() == (True, None, 0)

    @pytest.mark.parametrize('clsDatabase', allEngines)
    def test_add_get(self, clsDatabase):
        """
        Add data and verify that 'reset' flushes it.
        """
        db = clsDatabase(name=('test1', 'test2'))

        # Reset the database and verify that it is empty.
        assert db.reset().ok and db.count().data == 0

        # Insert two documents and verify the document count.
        ops = {
            '1': {'exists': False, 'data': {'key1': 'value1'}},
            '2': {'exists': False, 'data': {'key2': 'value2'}},
        }
        assert db.put(ops) == (True, None, {'1': True, '2': True})
        assert db.count() == (True, None, 2)
            
        # Fetch the content via three different methods.

        # getOne:
        assert db.getOne('1') == (True, None, ops['1']['data'])
        assert db.getOne('2') == (True, None, ops['2']['data'])

        # getMulti:
        tmp = {'1': ops['1']['data'], '2': ops['2']['data']}
        assert db.getMulti(['1', '2']) == (True, None, tmp)

        # getAll:
        assert db.getMulti(['1', '2']) == db.getAll()

        assert db.reset().ok and (db.count().data == 0)

    def test_projection(self):
        db = database.DatabaseInMemory(name=('test1', 'test2'))

        src = {'x': 1, 'a': {'b0': 2, 'b1': 3}, 'c': {'d': {'e': 3}}}
        assert db.project(src, [['z']]) == {}
        assert db.project(src, [['x']]) == {'x': 1}
        assert db.project(src, [['x'], ['a']]) == {'x': 1, 'a': {'b0': 2, 'b1': 3}}
        assert db.project(src, [['x'], ['a', 'b0']]) == {'x': 1, 'a': {'b0': 2}}
        assert db.project(src, [['x'], ['a', 'b5']]) == {'x': 1}
        assert db.project(src, [['c']]) == {'c': {'d': {'e': 3}}}
        assert db.project(src, [['c', 'd']]) == {'c': {'d': {'e': 3}}}
        assert db.project(src, [['c', 'd', 'e']]) == {'c': {'d': {'e': 3}}}
        assert db.project(src, [['c', 'd', 'blah']]) == {}

    @pytest.mark.parametrize('clsDatabase', allEngines)
    def test_get_with_projections(self, clsDatabase):
        """
        Add data and verify that 'reset' flushes it.
        """
        db = clsDatabase(name=('test1', 'test2'))

        # Reset the database and verify that it is empty.
        assert db.reset().ok and db.count().data == 0

        # Insert two documents and verify the document count.
        doc = {
            'foo': {'x': {'y0': 0, 'y1': 1}},
            'bar': {'a': {'b0': 2, 'b1': 3}},
        }
        ops = {'1': {'exists': False, 'data': doc}}
        assert db.put(ops) == (True, None, {'1': True})
        assert db.count() == (True, None, 1)
            
        # Fetch the content via getOne.

        assert db.getOne('1', [['blah']]) == (True, None, {})

        ret = db.getOne('1', [['foo', 'x']])
        assert ret.ok
        assert ret.data == {'foo': {'x': {'y0': 0, 'y1': 1}}}

        ret = db.getOne('1', [['foo', 'x', 'y0']])
        assert ret.ok
        assert ret.data == {'foo': {'x': {'y0': 0}}}

        # Fetch the content via getMulti.

        assert db.getMulti(['1'], [['blah']]) == (True, None, {'1': {}})

        ret = db.getMulti(['1'], [['foo', 'x']])
        assert ret.ok
        assert ret.data == {'1': {'foo': {'x': {'y0': 0, 'y1': 1}}}}

        ret = db.getMulti(['1'], [['foo', 'x', 'y0']])
        assert ret.ok
        assert ret.data == {'1': {'foo': {'x': {'y0': 0}}}}

        # Fetch the content via getAll. For simplicity, just verify that the
        # output matched that of getMult since we just tested that that one
        # worked.
        projections = [ [['blah']], [['foo', 'x']], [['foo', 'x', 'y0']] ]
        for prj in projections:
            assert db.getMulti(['1'], prj) == db.getAll(prj)

    def test_hasKey(self):
        db = database.DatabaseInMemory(name=('test1', 'test2'))

        src = {'x': 1, 'a': {'b': 2}, 'c': {'d': {'e': 3}}}
        assert not db.hasKey(src, ['z'])
        assert not db.hasKey(src, ['x', 'a'])
        assert not db.hasKey(src, ['a', 'x'])
        assert db.hasKey(src, ['x'])
        assert db.hasKey(src, ['a'])
        assert db.hasKey(src, ['c'])
        assert db.hasKey(src, ['a', 'b'])
        assert db.hasKey(src, ['c', 'd'])
        assert db.hasKey(src, ['c', 'd', 'e'])

    def test_delKey(self):
        db = database.DatabaseInMemory(name=('test1', 'test2'))

        src = {'x': 1, 'a': {'b': 2}, 'c': {'d': {'e': 3}}}

        db.delKey(src, ['z'])
        assert src == {'x': 1, 'a': {'b': 2}, 'c': {'d': {'e': 3}}}

        db.delKey(src, ['x'])
        assert src == {'a': {'b': 2}, 'c': {'d': {'e': 3}}}

        db.delKey(src, ['a'])
        assert src == {'c': {'d': {'e': 3}}}

        db.delKey(src, ['c', 'd'])
        assert src == {'c': {}}

        db.delKey(src, ['c'])
        assert src == {}

    def test_setKey(self):
        db = database.DatabaseInMemory(name=('test1', 'test2'))

        src = {'x': 1, 'a': {'b': 2}, 'c': {'d': {'e': 3}}}

        db.setKey(src, ['z'], -1)
        assert src == {'x': 1, 'a': {'b': 2}, 'c': {'d': {'e': 3}}, 'z': -1}

        db.setKey(src, ['x'], -1)
        assert src == {'x': -1, 'a': {'b': 2}, 'c': {'d': {'e': 3}}, 'z': -1}

        db.setKey(src, ['a'], -1)
        assert src == {'x': -1, 'a': -1, 'c': {'d': {'e': 3}}, 'z': -1}

        db.setKey(src, ['a'], {'b': -2})
        assert src == {'x': -1, 'a': {'b': -2}, 'c': {'d': {'e': 3}}, 'z': -1}

        db.setKey(src, ['c', 'd', 'e'], -2)
        assert src == {'x': -1, 'a': {'b': -2}, 'c': {'d': {'e': -2}}, 'z': -1}

    @pytest.mark.parametrize('clsDatabase', allEngines)
    def test_modify_single(self, clsDatabase):
        """
        Insert a single document and modify it.
        """
        db = clsDatabase(name=('test1', 'test2'))

        # Reset the database and verify that it is empty.
        assert db.reset().ok and db.count().data == 0

        doc = {
            'foo': {'a': 1, 'b': 2},
            'bar': {'c': 3, 'd': 2},
        }
        ops = {'1': {'exists': False, 'data': doc}}

        assert db.put(ops) == (True, None, {'1': True})

        ops = {
            '1': {
                'inc': {('foo', 'a'): 1, ('bar', 'c'): -1},
                'set': {('foo', 'b'): 20},
                'unset': [('bar', 'd')],
                'exists': {('bar', 'd'): True},
            }
        }
        assert db.mod(ops) == (True, None, {'1': True})

        ret = db.getOne('1')
        assert ret.ok
        ref = {
            'foo': {'a': 2, 'b': 20},
            'bar': {'c': 2},
        }
        assert ret.data == ref


if __name__ == '__main__':
    test_increment_WPCounter()
