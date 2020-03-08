import unittest

from cloudapi import cloudovh

class TestMethods(unittest.TestCase):
    @classmethod
    def isNotEmptyList(cls, l):
        unittest.TestCase().assertIsInstance(l, list)
        unittest.TestCase().assertTrue(l)

class TestsGeneric(unittest.TestCase):
    def test_projects(self):
        projects = cloudovh.projects(config_file="../ovh.conf")
        self.assertTrue(projects)

class TestsOVH(unittest.TestCase):
    def setUp(self):
        self.ovh = cloudovh.MyCloud(config_file="../ovh.conf")

    def test___init__(self):
        self.assertIsNotNone(cloudovh.CONFIG_PATH)
        for s in (self.ovh._projectname,
                  self.ovh._sshKeyId,
                  self.ovh._serviceName):
            self.assertIsInstance(s, str)
            self.assertTrue(s)

    def test_show_ip(self):
        r = self.ovh.show_ip()
        self.assertIsInstance(r, list)
        self.assertIsInstance(r[0], dict)

    def test_list_instances(self):
        TestMethods.isNotEmptyList(self.ovh.list_instances())

    def test_list_volumes(self):
        TestMethods.isNotEmptyList(self.ovh.list_volumes())

    def test_filter(self):
        flavor = self.ovh._default_flavor
        image = self.ovh._default_image
        region = self.ovh._default_region
        self.assertIs(1, len(self.ovh.flavor(
            filter={'name': flavor, 'region': region})))
        self.assertIs(1, len(self.ovh.image(
            filter={'name': image, 'region': region})))


if __name__ == '__main__':
    unittest.main()
