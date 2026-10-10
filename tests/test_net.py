import socket
import unittest
from unittest.mock import patch

from services import net


class StorageDiagnosisTests(unittest.TestCase):
    def test_reports_a_host_that_does_not_exist_without_exposing_it(self):
        def fake(host, port, family=0, type=0, proto=0, flags=0):
            if host == 'projetoantigo123.supabase.co':
                raise socket.gaierror(socket.EAI_NONAME, 'Name or service not known')
            return [('ok',)]

        with patch.object(net.socket, 'getaddrinfo', fake), \
                patch.object(net.urllib.request, 'urlopen', side_effect=OSError(-2, 'Name or service not known')):
            result = net.diagnose('https://projetoantigo123.supabase.co', 'projetoatual456')
        self.assertTrue(result['dns_ipv4'].startswith('erro'))
        self.assertEqual(result['dns_referencia_ipv4'], 'ok')
        self.assertFalse(result['igual_ao_projeto_informado'])
        self.assertEqual(result['dns_projeto_informado_ipv4'], 'ok')
        self.assertEqual(result['tipo_de_host'], 'Project URL do Supabase')
        self.assertNotIn('projetoantigo123', str(result))

    def test_flags_the_ipv6_only_database_host(self):
        with patch.object(net.socket, 'getaddrinfo', return_value=[('ok',)]), \
                patch.object(net.urllib.request, 'urlopen', side_effect=OSError(-2, 'x')):
            result = net.diagnose('https://db.abc.supabase.co')
        self.assertIn('banco direto', result['tipo_de_host'])
        self.assertNotIn('igual_ao_projeto_informado', result)

    def test_not_configured(self):
        self.assertEqual(net.diagnose(''), {'configurado': False})


if __name__ == '__main__':
    unittest.main()
