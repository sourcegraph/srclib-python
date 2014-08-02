import unittest
from graph import *

class Test_graph(unittest.TestCase):
    def test_filename_to_module_name(self):
        cases = [
            ('foo.py', 'foo'),
            ('foo/bar.py', 'foo.bar'),
            ('foo/__init__.py', 'foo'),
            ('foo/bar/__init__.py', 'foo.bar'),
            ('__init__.py', ''),
        ]

        for case in cases:
            filename, exp_module_name = case[0], case[1]
            act_module_name = filename_to_module_name(filename)
            self.assertEqual(exp_module_name, act_module_name, msg=('%s: %s != %s' % (filename, exp_module_name, act_module_name)))
