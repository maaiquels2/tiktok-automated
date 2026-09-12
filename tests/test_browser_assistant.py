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
        self.assertIn('--user-data-dir='+str(self.assistant.profile_root/'gen-maaiquels'), args)
        self.assertEqual(args[-1], 'https://grok.com/imagine')
        self.assertFalse(any('remote-debugging' in arg or 'enable-automation' in arg for arg in args))
        # Grok/Flow rodam em Chrome nativo: o modo reporta a origem da janela.
        self.assertEqual(result['mode'], 'native_chrome')
        self.assertEqual(repeated['profile'], 'gen-maaiquels')
        self.assertIsNone(self.assistant.playwright)
        # A primeira chamada abre a janela; a segunda entra como aba nela.
        self.assertEqual(popen.call_count, 2)
        self.assertIn('--new-window', popen.call_args_list[0].args[0])
        self.assertNotIn('--new-window', popen.call_args_list[1].args[0])

    def test_windows_side_by_side_error_is_actionable(self):
        error = OSError('Side by side configuration invalid')
        error.winerror = 14001
        with patch('services.browser_assistant.installed_browser', return_value=self.executable), \
             patch('services.browser_assistant.subprocess.Popen', side_effect=error):
            with self.assertRaisesRegex(RuntimeError, '14001'):
                self.assistant.open_grok_for_image(1)

    def test_grok_shares_the_generation_profile_with_flow(self):
        # Grok e Flow passaram a dividir a mesma janela (abas) no perfil de
        # geracao. Abrir o Grok com o Flow ativo deixou de ser um erro.
        self.assistant.contexts['gen-maaiquels'] = Mock()
        process = Mock()
        process.poll.return_value = None
        try:
            with patch('services.browser_assistant.installed_browser', return_value=self.executable), \
                 patch('services.browser_assistant.subprocess.Popen', return_value=process) as popen:
                result = self.assistant.open_grok_for_image(1)
                popen.assert_called_once()
            self.assertEqual(result['profile'], 'gen-maaiquels')
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

    def test_studio_reuses_local_profile_when_global_chrome_is_unavailable(self):
        local = self.assistant.profile_root / 'micaela-cdp'
        with patch.dict('os.environ', {}, clear=True), \
             patch('services.browser_assistant.installed_browser', return_value=self.executable), \
             patch('services.browser_assistant.existing_chrome_profile', side_effect=RuntimeError('Unavailable')), \
             patch.object(self.assistant, '_existing_factory_cdp_profile', return_value=local), \
             patch('services.browser_assistant.ensure_micaela_cdp_user_data') as clone, \
             patch('services.browser_assistant.kill_micaela_cdp_chrome') as kill, \
             patch('services.browser_assistant.subprocess.Popen') as popen, \
             patch.dict('sys.modules', {'playwright.async_api': None}):
            result = self.assistant.open_tiktok_studio(12)
        args = popen.call_args.args[0]
        self.assertIn('--user-data-dir='+str(local), args)
        self.assertEqual(args[-1], 'https://www.tiktok.com/tiktokstudio/upload')
        self.assertFalse(any('remote-debugging' in arg or 'no-sandbox' in arg for arg in args))
        self.assertEqual(result['campaign_id'], 12)
        clone.assert_not_called()
        kill.assert_not_called()
        self.assertIsNone(self.assistant.playwright)


if __name__ == '__main__':
    unittest.main()
