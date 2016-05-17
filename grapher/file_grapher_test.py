import unittest
from grapher.file_grapher import FileGrapher

class TestFileGrapher(unittest.TestCase):
    """
    Tests for FileGrapher.
    """
    def test_module_path_to_parent_module_name(self):
        """ Check if parent module name is correctly detected. """
        cases = [
            ('foo.py', ''),
            ('foo/bar.py', 'foo'),
            ('foo/__init__.py', ''),
            ('foo/bar/__init__.py', 'foo'),
            ('foo/bar/chocolate/__init__.py', 'foo.bar'),
            ('foo/bar/chocolate/crunchy.py', 'foo.bar.chocolate'),
            ('__init__.py', ''),
        ]
        for case in cases:
            filepath, exp_module_name = case[0], case[1]
            act_module_name = FileGrapher._get_module_parent_from_module_path(filepath)
            self.assertEqual(
                exp_module_name,
                act_module_name,
                msg=('{}: {} != {}'.format(filepath, exp_module_name, act_module_name))
            )
