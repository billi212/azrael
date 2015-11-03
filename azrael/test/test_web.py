import json
import pytest
import base64
import tornado.web
import tornado.testing
import azrael.web
import azrael.clerk
import azrael.config as config

from IPython import embed as ipshell
from azrael.aztypes import FragDae
from azrael.test.test import getFragRaw, getFragDae, getTemplate
from azrael.test.test import getCSBox, getCSSphere, getRigidBody


class TestWebServer(tornado.testing.AsyncHTTPTestCase):
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

    def get_app(self):
        # Dibbler instance is necessary because this test suite contains
        # several integration tests between Dibbler and WebServer.
        self.dibbler = azrael.dibbler.Dibbler()

        # Handler to serve up models.
        FH = azrael.web.MyGridFSHandler
        handlers = [(config.url_templates + '/(.*)', FH),
                    (config.url_instances + '/(.*)', FH)]
        return tornado.web.Application(handlers)

    def downloadFragRaw(self, url: str, fname: str):
        """
        Download and unpack the Raw model from ``url`` and return it as a
        ``FragRaw`` instance.

        Example: downloadFragRaw('/instances/3/raw1/')

        :param str url: download URL
        :return: Raw model
        :rtype: FragRaw
        :raises: AssertionError if there was a problem.
        """
        ret = self.fetch(url + fname, method='GET')
        try:
            data = base64.b64encode(ret.body).decode('utf8')
        except ValueError:
            assert False
        return FragDae(files={fname: data})

    def downloadFragDae(self, url: str, fnames: list):
        """
        fixme: docu

        Download and unpack the Collada model from ``url`` and return it as a
        ``FragDae`` instance.

        Example: downloadFragDae('/instances/1/name1/')

        :param str url: download URL
        :param str dae: name of Collada model.
        :param list textures: list of strings denoting the texture files.
        :return: Dae model
        :rtype: FragDae
        :raises: AssertionError if there was a problem.
        """
        # Download all the textures.
        fdata = {}
        for fname in fnames:
            fdata[fname] = self.fetch(url + fname, method='GET').body

        # Convert the fields to Base64 encode strings and construct a new
        # FragDae instance.
        b64enc = base64.b64encode
        fdata = {k: b64enc(v).decode('utf8') for (k, v) in fdata.items()}
        return FragDae(files=fdata)

    def verifyTemplate(self, url, fragments):
        """
        fixme: docu
        Raise an error if the ``fragments`` are not available at ``url``.

        This method automatically adapts to the fragment type and verifies
        the associated textures (if any).

        :param str url: base location of template
        :param list[FragMeta] fragments: reference fragments
        :raises: AssertionError if not all fragments in ``fragments`` match
                 those available at ``url``.
        """
        # Download- and verify each fragment.
        for aid, frag in fragments.items():
            ftype = frag.fragtype.upper()
            if ftype == 'RAW':
                tmp_url = url + '/{name}/'.format(name=aid)
                assert self.downloadFragRaw(tmp_url, 'model.json') == frag.fragdata
            elif ftype == 'DAE':
                tmp_url = url + '/{name}/'.format(name=aid)
                fnames = list(frag.fragdata.files.keys())
                ret = self.downloadFragDae(tmp_url, fnames)
                assert ret == frag.fragdata
            else:
                assert False

    def test_addTemplates(self):
        """
        Add and query a template with one Raw fragment.
        """
        self.dibbler.reset()
        azrael.database.init()
        clerk = azrael.clerk.Clerk()

        # Create two Templates. The first has only one Raw- and two
        # Collada geometries, the other has it the other way around.
        frags_t1 = {'foo1': getFragRaw(),
                    'bar2': getFragDae(),
                    'bar3': getFragDae()}
        frags_t2 = {'foo4': getFragRaw(),
                    'foo5': getFragRaw(),
                    'bar6': getFragDae()}
        body_a = getRigidBody(cshapes={'cssphere': getCSSphere()})
        body_b = getRigidBody(cshapes={'csbox': getCSBox()})
        t1 = getTemplate('t1', rbs=body_a, fragments=frags_t1)
        t2 = getTemplate('t2', rbs=body_b, fragments=frags_t2)
        del frags_t1, frags_t2

        # Add the first template.
        assert clerk.addTemplates([t1]).ok

        # Attempt to add the template a second time. This must fail.
        assert not clerk.addTemplates([t1]).ok

        # Verify the first template is available for download via WebServer.
        url_template = config.url_templates
        self.verifyTemplate('{}/t1'.format(url_template), t1.fragments)

        # Add the second template and verify both are available for download
        # via WebServer.
        assert clerk.addTemplates([t2]).ok
        self.verifyTemplate('{}/t1'.format(url_template), t1.fragments)
        self.verifyTemplate('{}/t2'.format(url_template), t2.fragments)

    def test_spawnTemplates(self):
        """
        Spawn a template and verify it is available via WebServer.
        """
        self.dibbler.reset()
        azrael.database.init()
        clerk = azrael.clerk.Clerk()

        # # Create two Templates. The first has only one Raw- and two
        # # Collada geometries, the other has it the other way around.
        frags_t1 = {'raw1': getFragRaw(),
                    'dae2': getFragDae(),
                    'dae3': getFragDae()}
        frags_t2 = {'raw4': getFragRaw(),
                    'raw5': getFragRaw(),
                    'dae6': getFragDae()}
        body_t1 = getRigidBody(cshapes={'cssphere': getCSSphere()})
        body_t2 = getRigidBody(cshapes={'csbox': getCSBox()})
        t1 = getTemplate('t1', rbs=body_t1, fragments=frags_t1)
        t2 = getTemplate('t2', rbs=body_t2, fragments=frags_t2)
        del frags_t1, frags_t2

        # Add both templates and verify they are available.
        assert clerk.addTemplates([t1, t2]).ok
        self.verifyTemplate('{}/t1'.format(config.url_templates), t1.fragments)
        self.verifyTemplate('{}/t2'.format(config.url_templates), t2.fragments)

        # No object instance with ID=1 must exist yet.
        url_inst = config.url_instances
        with pytest.raises(AssertionError):
            self.verifyTemplate('{}/{}'.format(url_inst, 1), t1.fragments)

        # Spawn the first template (it must get objID=1).
        ret = clerk.spawn([{'templateID': 't1', 'rbs': {'imass': 1}}])
        assert ret.data == (1, )
        self.verifyTemplate('{}/{}'.format(url_inst, 1), t1.fragments)

        # Spawn two more templates and very their instance models.
        new_objs = [{'templateID': 't2', 'rbs': {'imass': 1}},
                    {'templateID': 't1', 'rbs': {'imass': 1}}]
        ret = clerk.spawn(new_objs)
        assert ret.data == (2, 3)
        self.verifyTemplate('{}/{}'.format(url_inst, 2), t2.fragments)
        self.verifyTemplate('{}/{}'.format(url_inst, 3), t1.fragments)

    def test_updateFragments(self):
        """
        Modify the fragments of a spawned object.
        """
        self.dibbler.reset()
        azrael.database.init()
        clerk = azrael.clerk.Clerk()

        # Create two Templates. The first has only one Raw- and two
        # Collada geometries, the other has it the other way around.
        frags_old = {'name1': getFragRaw(),
                     'name2': getFragDae(),
                     'name3': getFragDae()}
        frags_new = {'name1': getFragDae(),
                     'name2': getFragDae(),
                     'name3': getFragRaw()}
        t1 = getTemplate('t1', fragments=frags_old)

        # Add-, spawn-, and verify the template.
        assert clerk.addTemplates([t1]).ok
        self.verifyTemplate('{}/t1'.format(config.url_templates), t1.fragments)
        ret = clerk.spawn([{'templateID': 't1', 'rbs': {'imass': 1}}])
        objID = 1
        assert ret.data == (objID, )

        # Verify that the instance has the old fragments, not the new ones.
        url_inst = config.url_instances
        self.verifyTemplate('{}/{}'.format(url_inst, 1), frags_old)
        with pytest.raises(AssertionError):
            self.verifyTemplate('{}/{}'.format(url_inst, 1), frags_new)

        # Update the fragments.
        tmp = {k: v._asdict() for (k, v) in frags_new.items()}
        clerk.setFragments({objID: tmp})

        # Verify that the object now has the new fragments. Then verify that
        # its old fragments are no longer available.
        self.verifyTemplate('{}/{}'.format(url_inst, 1), frags_new)

        # fixme: activate this code again when updating setFragments. Currently
        # the exception is not raised because no fragment were explicity
        # deleted (some files were merely overwritten).
#        with pytest.raises(AssertionError):
#            self.verifyTemplate('{}/{}'.format(url_inst, 1), frags_old)

    def test_deleteInstance(self):
        """
        Add/remove an instance from Dibbler via Clerk and verify via WebServer.
        """
        self.dibbler.reset()
        azrael.database.init()
        clerk = azrael.clerk.Clerk()

        # Create a Template.
        frags = {'name1': getFragRaw()}
        t1 = getTemplate('t1', fragments=frags)

        # Add-, spawn-, and verify the template.
        assert clerk.addTemplates([t1]).ok
        self.verifyTemplate('{}/t1'.format(config.url_templates), t1.fragments)
        ret = clerk.spawn([{'templateID': 't1', 'rbs': {'imass': 1}}])
        assert ret.data == (1, )

        # Verify that the instance exists.
        url_inst = config.url_instances
        self.verifyTemplate('{}/{}'.format(url_inst, 1), frags)

        # Delete the instance and verify it is now gone.
        cnt = self.dibbler.getNumFiles().data
        assert clerk.removeObject(objID=1) == (True, None, None)
        self.dibbler.getNumFiles().data == cnt - 2
        with pytest.raises(AssertionError):
            self.verifyTemplate('{}/{}'.format(url_inst, 1), frags)
