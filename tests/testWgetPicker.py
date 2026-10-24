# <copyright>
# (c) Copyright 2026 Autumn Patterson
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
"""WgetPicker against a real loopback HTTP directory index.

Covers the Python 3 conversion points: urllib2/urlparse -> urllib.request /
urllib.parse, decoding the *bytes* that urlopen().read() returns before the
text processing, and the raw-string ``\\g<...>`` regex substitutions.  The
final download step shells out to wget, so a fake wget that just records its
arguments is put first on PATH.
"""
import http.server
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

from tests import csmake_alias, fakes

WgetPicker = csmake_alias.import_module('CsmakeModules.WgetPicker').WgetPicker

INDEX = (
    b'<html><head><title>Index of /pkgs</title></head><body>\n'
    b'<h1>Index of /pkgs</h1><pre>\n'
    b'<a href="../">Parent Directory</a>\n'
    b'<a href="pkg-1.0.tar.gz">pkg-1.0.tar.gz</a>\n'
    b'<a href="pkg-1.10.tar.gz">pkg-1.10.tar.gz</a>\n'
    b'<a href="pkg-1.9.tar.gz">pkg-1.9.tar.gz</a>\n'
    b'<a href="spaced%20name-2.0.tar.gz">spaced name-2.0.tar.gz</a>\n'
    + u'<a href="caf%C3%A9-1.0.tar.gz">café-1.0.tar.gz</a>\n'.encode('utf-8')
    + b'<a name="top">an anchor without an href</a>\n'
    b'<a href="stray-\xff.txt">not valid utf-8</a>\n'
    b'</pre></body></html>\n')

FAKE_WGET = """#!/bin/sh
# Record "<output path> <url>" and create the output file, like wget -O would.
out=""
prev=""
url=""
for arg in "$@"; do
    if [ "$prev" = "-O" ]; then out="$arg"; fi
    prev="$arg"
    url="$arg"
done
echo "$out $url" >> "$FAKE_WGET_LOG"
if [ -n "$out" ]; then : > "$out"; fi
"""


class _IndexHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/pkgs/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(INDEX)))
            self.end_headers()
            self.wfile.write(INDEX)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


class TestWgetPicker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(('127.0.0.1', 0), _IndexHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()
        cls.base = 'http://127.0.0.1:%d' % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swak-wget-')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bindir = os.path.join(self.tmp, 'bin')
        os.mkdir(bindir)
        fakes.write_executable(bindir, 'wget', FAKE_WGET)
        self.wgetLog = os.path.join(self.tmp, 'wget.log')
        # Keep urllib off any proxy configured on the developer's machine so
        # loopback requests stay loopback.
        environ = dict(
            (k, v) for k, v in os.environ.items()
            if not k.lower().endswith('_proxy'))
        environ['no_proxy'] = '127.0.0.1'
        environ['FAKE_WGET_LOG'] = self.wgetLog
        environ['PATH'] = bindir + os.pathsep + environ.get('PATH', '')
        patcher = mock.patch.dict(os.environ, environ, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.results = os.path.join(self.tmp, 'results')
        os.mkdir(self.results)
        self.picker = WgetPicker(fakes.FakeEnv(self.results), fakes.FakeLog())

    def wgetCalls(self):
        with open(self.wgetLog) as f:
            return [line.rstrip('\n').split(' ', 1) for line in f]

    def test_directory_index_links_are_decoded_and_parsed(self):
        # Exercises urllib.request (both the proxy-honouring urlopen path and
        # the explicit no-proxy opener), bytes -> str decoding, urllib.parse.unquote.
        expected = [
            ['../', 'Parent Directory'],
            ['pkg-1.0.tar.gz', 'pkg-1.0.tar.gz'],
            ['pkg-1.10.tar.gz', 'pkg-1.10.tar.gz'],
            ['pkg-1.9.tar.gz', 'pkg-1.9.tar.gz'],
            ['spaced name-2.0.tar.gz', 'spaced name-2.0.tar.gz'],
            [u'café-1.0.tar.gz', u'café-1.0.tar.gz'],
            # invalid UTF-8 is replaced rather than aborting the whole listing
            [u'stray-�.txt', u'not valid utf-8'],
        ]
        for useProxy in (False, True):
            with self.subTest(useProxy=useProxy):
                self.picker.useProxy = useProxy
                self.assertEqual(
                    expected, self.picker._doPull(self.base + '/pkgs'))

    def test_format_order_and_pick_select_the_download(self):
        # Exercises the raw-string \g<sub>/\g<follow> substitutions that turn
        # 'pkg-{version}.tar.gz' into a glob plus a named-group regex.
        local = os.path.join(self.tmp, 'landing')
        picked = self.picker.pull({
            'URL': self.base + '/pkgs/',
            'no-proxy': 'True',
            'format': 'pkg-{version}.tar.gz',
            'order': 'large->small:version',
            'pick': 'first:2',
            'local': local})
        self.assertEqual(
            [{'version': '1.9'}, {'version': '1.10'}],
            [link[0] for link in picked])
        self.assertEqual(
            [[os.path.join(local, 'pkg-1.9.tar.gz'),
              self.base + '/pkgs/pkg-1.9.tar.gz'],
             [os.path.join(local, 'pkg-1.10.tar.gz'),
              self.base + '/pkgs/pkg-1.10.tar.gz']],
            self.wgetCalls())
        self.assertEqual('passed', self.picker.log.result)

    def test_pick_item_filters_on_a_format_tag(self):
        picked = self.picker.pull({
            'URL': self.base + '/pkgs/',
            'no-proxy': 'True',
            'format': 'pkg-{version}.tar.gz',
            'pick': 'item:version=1.10',
            'local': self.results})
        self.assertEqual([{'version': '1.10'}], [link[0] for link in picked])
        self.assertEqual(
            [[os.path.join(self.results, 'pkg-1.10.tar.gz'),
              self.base + '/pkgs/pkg-1.10.tar.gz']],
            self.wgetCalls())

    def test_ordering_the_whole_string_does_not_compare_tag_dicts(self):
        # 'order' without an <item> orders by the entire link string.  Python 3
        # cannot compare the per-link tag dicts, which Python 2 silently could,
        # so sorting on those dicts raised TypeError for any format with tags.
        picked = self.picker.pull({
            'URL': self.base + '/pkgs/',
            'no-proxy': 'True',
            'format': 'pkg-{version}.tar.gz',
            'order': 'large->small',
            'pick': 'first:1',
            'local': self.results})
        self.assertEqual([{'version': '1.9'}], [link[0] for link in picked])


if __name__ == '__main__':
    unittest.main()
