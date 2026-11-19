import tempfile
import unittest
import subprocess
import sys
import shutil
from pathlib import Path
import project_instruction_reference as m

class Tests(unittest.TestCase):
    def test_generated_claude_preserves_all_original_text(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'CLAUDE.md';original='# Existing\nKeep project build rules.\n';p.write_text(original)
            r=m.run(d,'apple','install');self.assertEqual(r['files'],['CLAUDE.md']);self.assertTrue(p.read_text().startswith(original));self.assertTrue(m.valid(p.read_text()))
    def test_agents_convention_no_extra_claude_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'AGENTS.md';p.write_text('Native Codex instructions')
            self.assertEqual(m.run(d,'apple','install')['files'],['AGENTS.md']);self.assertFalse((Path(d)/'CLAUDE.md').exists())
    def test_both_existing_files_preserved_and_checked(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ['AGENTS.md','CLAUDE.md']:(Path(d)/n).write_text(n+' original')
            self.assertEqual(len(m.run(d,'apple','install')['files']),2)
            self.assertTrue(m.run(d,'apple','check')['verified'])
    def test_explicit_new_codex_convention(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(m.run(d,'apple','install','AGENTS.md')['files'],['AGENTS.md'])
            self.assertFalse((Path(d)/'CLAUDE.md').exists())
    def test_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            m.run(d,'apple','install');p=Path(d)/'CLAUDE.md';before=p.read_bytes();m.run(d,'apple','install');self.assertEqual(before,p.read_bytes())
    def test_missing_reference_fails_closeout(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'CLAUDE.md').write_text('Only generic instructions')
            with self.assertRaises(ValueError):m.run(d,'apple','check')
    def test_edited_managed_block_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'CLAUDE.md';p.write_text(m.START+'\nUser edit\n'+m.END)
            before=p.read_bytes()
            with self.assertRaises(ValueError):m.run(d,'apple','install')
            self.assertEqual(before,p.read_bytes())
    def test_missing_instruction_with_intact_markers_and_references_fails_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'AGENTS.md'
            edited = m.BLOCK.replace('Maintain the existing project implementation/evidence record automatically;\n', '')
            p.write_text(edited)
            for mode in ['check', 'install']:
                result = subprocess.run([sys.executable, str(m.__file__), mode, '--project', d, '--platform', 'apple'],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('AGENTS.md: existing support-reference block', result.stderr)
                self.assertEqual(p.read_text(), edited)

    def test_windows_line_endings_are_preserved_and_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'AGENTS.md'
            original = b'# Existing\r\nPreserve these instructions.\r\n'
            p.write_bytes(original)
            m.run(d, 'apple', 'install')
            self.assertEqual(p.read_bytes(), original + b'\r\n' + m.BLOCK.replace('\n', '\r\n').encode())
            self.assertTrue(m.run(d, 'apple', 'check')['verified'])
    def test_non_apple_no_files_created(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(m.run(d,'other','install')['skipped']);self.assertEqual(list(Path(d).iterdir()),[])
    def test_no_cache_or_host_specific_paths_in_generated_reference(self):
        self.assertNotIn('/Users/',m.BLOCK);self.assertNotIn('/cache/',m.BLOCK);self.assertIn(m.REFERENCE,m.BLOCK)
    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            external=Path(d)/'external.md';external.write_text('untouched');(Path(d)/'AGENTS.md').symlink_to(external)
            with self.assertRaises(ValueError):m.run(d,'apple','install')
            self.assertEqual(external.read_text(),'untouched')
    def test_cli_verifies_written_and_bundled_reference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);script=root/'apple-dev/skills/project-kickoff/scripts/project_instruction_reference.py';script.parent.mkdir(parents=True);shutil.copyfile(m.__file__,script)
            reference=root/'apple-dev/references/app-support-entries.md';reference.parent.mkdir();reference.write_text('Canonical')
            project=root/'project';project.mkdir();(project/'AGENTS.md').write_text('Original rules')
            for mode in ['install','check']:
                result=subprocess.run([sys.executable,str(script),mode,'--project',str(project),'--platform','apple'],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr);self.assertIn('"bundle_reference_verified": true',result.stdout)
            self.assertTrue((project/'AGENTS.md').read_text().startswith('Original rules'))
    def test_cli_missing_bundle_fails_before_write(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);script=root/'apple-dev/skills/project-kickoff/scripts/project_instruction_reference.py';script.parent.mkdir(parents=True);shutil.copyfile(m.__file__,script);project=root/'project';project.mkdir()
            result=subprocess.run([sys.executable,str(script),'install','--project',str(project),'--platform','apple'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse((project/'CLAUDE.md').exists())

if __name__=='__main__':unittest.main()
