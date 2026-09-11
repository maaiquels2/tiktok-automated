import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from services.browser_assistant import BrowserAssistant, installed_browser, existing_chrome_profile


class BrowserAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.assistant = BrowserAssistant(root/'profiles', root/'media')
        self.executable = str(root/'Chrome'/'chrome.exe')

    def tearDown(self):
        self.assistant.close()
        self.assistant.close()  # Explicit cleanup and atexit must be idempotent.
        self.assertTrue(self.assistant.loop.is_closed())
        self.temp.cleanup()

    def test_grok_uses_native_browser_without_playwright(self):
        process = Mock()
        process.poll.return_value = None
        with patch('services.browser_assistant.installed_browser', return_value=self.executable), \
             patch('services.browser_assistant.subprocess.Popen', return_value=process) as popen, \
             patch.dict('sys.modules', {'playwright.async_api': None}):
            result = self.assistant.open_grok_for_image(12)
            repeated = self.assistant.open_grok_for_video(12)
        args = popen.call_args.args[0]
        self.assertEqual(args[0], self.executable)
        self.assertIn('--user-data-dir='+str(self.assistant.profile_root/'flow-maaiquels'), args)
        self.assertEqual(args[-1], 'https://grok.com/imagine')
        self.assertFalse(any('remote-debugging' in arg or 'enable-automation' in arg for arg in args))
        self.assertEqual(result['mode'], 'manual')
        self.assertEqual(repeated['profile'], 'flow-maaiquels')
        self.assertIsNone(self.assistant.playwright)
        popen.assert_called_once()

    def test_windows_side_by_side_error_is_actionable(self):
        error = OSError('Side by side configuration invalid')
        error.winerror = 14001
        with patch('services.browser_assistant.installed_browser', return_value=self.executable), \
             patch('services.browser_assistant.subprocess.Popen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, '14001'):
                self.assistant.open_grok_for_image(1)

    def test_grok_refuses_active_flow_profile(self):
        self.assistant.contexts['flow-maaiquels'] = Mock()
        try:
            with patch('services.browser_assistant.installed_browser', return_value=self.executable), \
                 patch('services.browser_assistant.subprocess.Popen') as popen:
                with self.assertRaisesRegex(RuntimeError, 'Feche todas as janelas do Flow'):
                    self.assistant.open_grok_for_image(1)
                popen.assert_not_called()
        finally:
            self.assistant.contexts.clear()

    def test_missing_browser_has_clear_message(self):
        with patch('services.browser_assistant.Path.is_file', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'Chrome ou Edge não encontrado'):
                installed_browser()

    def test_existing_micaela_profile_is_resolved_from_labels_only(self):
        root = Path(self.temp.name)/'User Data'
        root.mkdir()
        (root/'Local State').write_text('{"profile":{"info_cache":{"Default":{"name":"Maikel"},"Profile 6":{"name":"Micaela Meier","user_name":"micaela@example.com"}}}}',encoding='utf-8')
        with patch.dict('os.environ',{'FABRICA_CHROME_USER_DATA':str(root)},clear=False):
            resolved_root,resolved_profile=existing_chrome_profile()
        self.assertEqual(resolved_root,root)
        self.assertEqual(resolved_profile,'Profile 6')

    def test_studio_uses_existing_profile_without_playwright(self):
        process=Mock()
        process.poll.return_value=None
        root=Path(self.temp.name)/'User Data'
        root.mkdir()
        (root/'Local State').write_text('{"profile":{"info_cache":{"Profile 6":{"name":"Micaela Meier"}}}}',encoding='utf-8')
        with patch('services.browser_assistant.installed_browser',return_value=self.executable), \
             patch('services.browser_assistant.existing_chrome_profile',return_value=(root,'Profile 6')), \
             patch('services.browser_assistant.subprocess.Popen',return_value=process) as popen:
            result=self.assistant.open_tiktok_studio(12)
        args=popen.call_args.args[0]
        self.assertIn('--user-data-dir='+str(root),args)
        self.assertIn('--profile-directory=Profile 6',args)
        self.assertEqual(result['mode'],'existing')
        self.assertIsNone(self.assistant.playwright)


if __name__ == '__main__':
    unittest.main()
