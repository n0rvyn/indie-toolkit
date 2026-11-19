"""Guard the shared state-cleanup rule's consumers and the iOS harness boundary."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
class Tests(unittest.TestCase):
    def test_guidance_reaches_actual_testing_consumers(self):
        for relative in ['references/testing-guide.md','references/apple-swift-rules.md','skills/apple-swift-context/SKILL.md','skills/runtime-feature-verify/SKILL.md','skills/swiftui-visual-audit/SKILL.md']:
            self.assertIn('xc-ui-test-guide.md',(ROOT/relative).read_text(),relative)
        rule=(ROOT/'references/xc-ui-test-guide.md').read_text().split('## 0. Physical XCTest state restoration',1)[1].split('<!-- section: 1.',1)[0]
        for text in ['portraitUpsideDown','landscapeLeft','landscapeRight','unknown/faceUp/faceDown','Hard process termination','cleanup pending','rotation lock','permissions','verification']:
            self.assertIn(text,rule)
    def test_ios_cleanup_registration_precedes_launch_and_rotation(self):
        source=(ROOT/'skills/swiftui-visual-audit/SKILL.md').read_text()
        ios=source.split('### iOS\n',1)[1]
        launch=ios.split('func launch(_ mode: String)',1)[1].split('func shoot',1)[0]
        self.assertLess(launch.index('let prior'),launch.index('app.launch()'))
        self.assertLess(launch.index('addTeardownBlock'),launch.index('app.launch()'))
        self.assertIn('meaningful.contains(prior) ? prior : .portrait',launch)
        self.assertIn('orientation = restore',launch)
        mac=source.split('### iOS\n',1)[0]
        self.assertNotIn('let meaningful: [UIDeviceOrientation]',mac)
    def test_hard_kill_never_promised_teardown(self):
        rule=(ROOT/'references/xc-ui-test-guide.md').read_text()
        self.assertIn('Never promise teardown always ran',rule)
        self.assertIn('before closing the task',rule)

if __name__=='__main__':unittest.main()
