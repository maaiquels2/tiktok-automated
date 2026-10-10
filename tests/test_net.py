import errno
import socket
import unittest
from unittest.mock import patch

from services import net


class Ipv4FallbackTests(unittest.TestCase):
    def test_busy_mixed_lookup_retries_with_ipv4_only(self):
        calls = []

        def fake(host, port, family=0, type=0, proto=0, flags=0):
            calls.append(family)
            if family == socket.AF_UNSPEC:
                raise OSError(errno.EBUSY, 'Device or resource busy')
            return [('ipv4',)]

        with patch.object(net, '_original_getaddrinfo', fake):
            self.assertEqual(net._getaddrinfo_with_ipv4_fallback('x.supabase.co', 443), [('ipv4',)])
        self.assertEqual(calls, [socket.AF_UNSPEC, socket.AF_INET])

    def test_other_errors_are_not_hidden(self):
        def fake(host, port, family=0, type=0, proto=0, flags=0):
            raise socket.gaierror(socket.EAI_NONAME, 'Name or service not known')

        with patch.object(net, '_original_getaddrinfo', fake):
            with self.assertRaises(socket.gaierror):
                net._getaddrinfo_with_ipv4_fallback('nao-existe.invalid', 443)

    def test_explicit_family_is_never_rewritten(self):
        def fake(host, port, family=0, type=0, proto=0, flags=0):
            raise OSError(errno.EBUSY, 'Device or resource busy')

        with patch.object(net, '_original_getaddrinfo', fake):
            with self.assertRaises(OSError):
                net._getaddrinfo_with_ipv4_fallback('x.supabase.co', 443, socket.AF_INET6)

    def test_diagnose_reports_without_exposing_the_host(self):
        def fake(host, port, family=0, type=0, proto=0, flags=0):
            if family == socket.AF_UNSPEC:
                raise OSError(errno.EBUSY, 'Device or resource busy')
            return [('ok',)]

        with patch.object(net, '_original_getaddrinfo', fake), \
                patch.object(net.urllib.request, 'urlopen', side_effect=OSError(errno.ECONNREFUSED, 'recusada')):
            result = net.diagnose('https://segredo123.supabase.co')
        self.assertEqual(result['dns_misto'], 'erro 16: Device or resource busy')
        self.assertEqual(result['dns_ipv4'], 'ok')
        self.assertNotIn('segredo123', str(result))
        self.assertEqual(net.diagnose(''), {'configurado': False})


if __name__ == '__main__':
    unittest.main()
