import tempfile
import unittest
from pathlib import Path
import read_support_reference as m

class Tests(unittest.TestCase):
    def fixture(self,root):
        package=root/'apple-dev';script=package/'skills/app-support-entries/scripts/read_support_reference.py';script.parent.mkdir(parents=True);script.touch()
        reference=package/'references/app-support-entries.md';reference.parent.mkdir();reference.write_text('Single canonical checklist')
        return script,reference
    def test_package_relative_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            script,reference=self.fixture(Path(d));self.assertEqual(m.resolve_reference(script),reference.resolve())
    def test_discovery_symlink_uses_real_package(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);script,reference=self.fixture(root);alias=root/'.agents/skills/app-support-entries';alias.parent.mkdir(parents=True);alias.symlink_to(script.parent.parent,target_is_directory=True)
            self.assertEqual(m.resolve_reference(alias/'scripts/read_support_reference.py'),reference.resolve())
    def test_missing_reference_does_not_fall_back_to_cache(self):
        with tempfile.TemporaryDirectory() as d:
            script,reference=self.fixture(Path(d));reference.unlink()
            with self.assertRaises(ValueError):m.resolve_reference(script)

if __name__=='__main__':unittest.main()
