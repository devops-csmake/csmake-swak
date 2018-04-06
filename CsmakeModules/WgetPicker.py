# <copyright>
# (c) Copyright 2018 Cardinal Peak Technologies
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
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
from Csmake.CsmakeModule import CsmakeModule
import urlparse
import urllib2
import re
import fnmatch
import os.path
import subprocess

class WgetPicker(CsmakeModule):
    """Purpose: To get files from an http directory listing
       Type: Module   Library: csmake-swak
       Options:
            URL - url path to the directory listing
            no-error - (OPTIONAL) will not give a build error if no links match
                                  when True
                 Default: False
            use-text - (OPTIONAL) directs WgetPicker to use the anchor's
                 text (what you actually see in a web browser)
                 rather than the href (the actual link) when True
                 Default: False
                 Notes: This is helpful when the links are odd, or
                        don't parallel the actual names of the files.
                        Bookmarks ('#') in links are *not* ignored.
            ignore-link-paths - (OPTIONAL) When True, the link (or text)
                 will ignore everything to the left of the last '/'
                 in the link text for the filters.
                 Default: False
                 Notes: This can be helpful when the actual links or text
                        contain odd or complex paths.
                        If you specify a format, paths must be taken into
                        account.
            format - (OPTIONAL)
                 The format of the filenames match the format uses a glob style 
                   (shell style wildcards)
                 Also, tags can be used to specify a part of the filename to
                   pick or sort using curly braces ('{' and '}').
                 Tags can be called out in the 'order' and 'pick' options
                   for further filtering
                 If it's helpful:
                   You can think of a tag as a named splat ('*')
                 Default: Every link returned by the URL
                 Notes: Tags (like '*') are greedy, for example {a}.{b}
                    for a string 1.5.4.tar.gz will match up:
                          a = 1.5.4.tar
                          b = gz
            order - (OPTIONAL) Specify an ordering for the format's tags
                 usage: <direction>:<item>,<item>...
                   direction: either large->small or small->large
                     TODO: consider others like natural
                     TODO: consider multiple order specs
                           (CURRENTLY only one spec is allowed)
                   item: a tag in the format
                         (if 'item' not given, the ordering will apply to
                          the entire string)
                 example: 
                   order=small->large:myitem
                 Default order is whatever is given by the server in
                   page order.
            pick - (OPTIONAL)
                 Specify which files to pick from the listing returned from URL
                    as filtered by "format" and "order" options, if provided.
                 Multiple picks will be applied in the order provided.
                 Multiple picks are either semi-colon (';') or newline delimited
                 usage: <spec>:<info>
                    either newline or semi-colon separated
                  spec:info types:
                    item:<item>=<value>
                       will filter in any links that match
                       item - a tag in the format
                       value - a matching string
                       TODO: Consider other operators besides '='
                    first:<number>
                       will take the top <number> in the order of links that
                       match the format and previous pick filters.
                    last:<number>
                       will take the bottom <number> in the order of links
                       that match the format and previous pick filters.
            local - (OPTIONAL) Specify the directory to land the files locally
                    Default: %(RESULTS)s directory
            no-proxy - (OPTIONAL) When True, the proxy settings in the
                       environment will be ignored.
                       Default: False
       Phases:
            pull, download  - pull specified file(s)
       Example:
            [WgetPicker@my-html-pull]
            URL=https://pypi.python.org/simple/cartographer
            use-text=True
            format=cartographer-{version}.tar.gz
            pick=first:3
            order=large->small:version

            This will get the 3 items matching the format string
               with the highest versions (lexicographically).

            [WgetPicker@my-lucky-pull]
            URL=https://pypi.python.org/simple/cartographer
            pick=last:1

            This is a bit like google's "I'm feeling lucky" button :)
            This will give you the last link listed on the page.

            [WgetPicker@third-and-fourth-pick]
            URL=https://pypi.python.org/simple/cartographer
            pick=
                first:4
                last:2

            This gets the third and fourth link from the URL
        """

    REQUIRED_OPTIONS = ['URL']

    linkre = re.compile(r'\s*=\s*(\"|\')(?P<link>[^"]*)(\"|\')')
    READ_BUFFER_SIZE=102400

    def _doPull(self, url):
        success = False
        if url[-1] != '/':
            url += '/'

        buf = []
        links = []

        self.log.info("Reading URL: %s", url)

        if not self.useProxy:
            proxies = urllib2.ProxyHandler({})
            opener = urllib2.build_opener(proxies)
            req = urllib2.Request(url)
            fd = opener.open(req)
        else:
            fd = urllib2.urlopen(url)

        r = fd.read()
        while len(r) != 0:
            buf.append(r)
            r = fd.read()
        fd.close()
        self.log.devdebug("Page requested: %s", url)
        self.log.devdebug("Page pulled:\n%s", buf)
        success = True
        self.url = url
        self.exc_info = None

        buf = ''.join(buf).split('<a ')[1:]
        buf = [ x.split('</a')[0].split('>',1) for x in buf ]
        self.log.devdebug("Link parts: %s", str(buf))
        for link in buf:
            #NOTE: It may be more correct to split on '=' and get the
            #      href that way.
            parts = link[0].split('href',1)
            if len(parts) < 2:
                self.log.info("Link from '%s' malformed: %s", url, str(link))
                continue
            match = self.linkre.match(parts[1])
            if match is None:
                self.log.info("Link href from '%s' malformed: %s", url, str(link))
                continue
            linkmatch = match.group('link')
            if linkmatch is not None:
                linkmatch = urllib2.unquote(linkmatch)
            links.append([linkmatch, link[1].split("#")[0]])
        return links

    def _filter_first(self, options, links, filterParams):
        try:
            count = int(filterParams)
        except ValueError:
            self.log.error("filter 'first:%s' did not get an integer", filterParams)
            return links
        count = min(count, len(links))
        return links[:count]

    def _filter_last(self, options, links, filterParams):
        try:
           count = int(filterParams)
        except ValueError:
            self.log.error("filter 'last:%s' did not get an integer", filterParams)
            return links
        count = min(count, len(links))
        return links[-count:]

    def _filter_item(self, options, links, filterParams):
        result = []
        #TODO: consider other operators besides '='
        paramParts = filterParams.split('=',1)
        if len(paramParts) != 2:
            self.log.error("filter 'item:%s' expected format: <item>=<value>", filterParams)
        for link in links:
            groups = link[0]
            if paramParts[0] not in groups:
                self.log.error("filter 'item:%s' item '%s' was not found", filterParams, paramParts[0])
                continue
            if groups[paramParts[0]].strip() == paramParts[1].strip():
                result.append(link)
        return result

    def download(self, options):
        return self.pull(options)

    def pull(self, options):
        self.useProxy = True
        if 'no-proxy' in options:
            self.useProxy = options['no-proxy'] != 'True'
        try:
            #Pull the directory listing specified in the url
            links = self._doPull(options['URL'])
            partindex = 0
            if 'use-text' in options:
                partindex = 1 if options['use-text'] == 'True' else 0

            for link in links:
                link.append(link[partindex])

            ignorepath = False
            if 'ignore-link-paths' in options:
                ignorepath = options['ignore-link-paths'] == 'True'
            if ignorepath:
                for link in links:
                    link[-1] = link[-1].split('/')[-1]

            self.log.devdebug("Links after pull: %s", str(links))

            #Apply format re to get all matches
            formatFiltered = []
            if 'format' in options:
                formatGlob = CsmakeModule.BRACKET_RE.sub("*\g<follow>", options['format']).replace('}}','}')
                formatRE = re.compile(CsmakeModule.BRACKET_RE.sub('(?P<\g<sub>>.*)\g<follow>',fnmatch.translate(options['format']).replace('\\}','}').replace('\\{','{')).replace('}}','\\}'))
                for link in links:
                    if fnmatch.fnmatch(link[-1], formatGlob):
                        formatFiltered.append(link)
            else:
                formatFiltered = links
                formatRE = re.compile('.*')

            #Get the group dicts into the links list
            for link in formatFiltered:
                match = formatRE.match(link[-1])
                if match is None:
                    self.log.error("link '%s' was expected to match '%s'", link[-1], formatRE)
                    continue
                groups = match.groupdict()
                link.insert(0, groups)

            self.log.devdebug("Links after format: %s", str(formatFiltered))

            #Order the list of matches according to the spec
            if 'order' in options:
                orderParts = options['order'].split(':')
                orderString = len(orderParts) == 1 \
                              or len(orderParts[1].strip()) == 0
                indexedList = []
                if not orderString:
                    orderItems = orderParts[1].split(',')
                    orderItems = [ x.strip() for x in orderItems ]
                    for index, link in enumerate(formatFiltered):
                        groups = link[0]
                        indexitems = []
                        for item in orderItems:
                            if item not in groups:
                                self.log.error("{%s} was expected in '%s'", item, link[-1])
                                indexitems.append(None)
                            else:
                                indexitems.append(groups[item])
                        indexitems.append(index)
                        indexedList.append(indexitems)
                else:
                    for index, link in enumerate(formatFiltered):
                        indexedList.append([link,index])
                indexedList.sort()
                if orderParts[0].strip() == 'large->small':
                    indexedList.reverse()

                orderedList = []
                for item in indexedList:
                    orderedList.append(formatFiltered[item[-1]])
                formatFiltered = orderedList

            self.log.devdebug("Links after order: %s", str(formatFiltered))

            #Apply pick filters in order
            if 'pick' in options:
                picks = ';'.join(options['pick'].split('\n')).split(';')
                for pick in picks:
                    pick = pick.strip()
                    if len(pick) == 0:
                        continue
                    pickparts = pick.split(':',1)
                    if len(pickparts) != 2:
                        self.log.error("pick entries need a <spec>:<info> format")
                        self.log.error("   - got: %s", pick)
                    method = "_filter_%s" % pickparts[0].strip()
                    if not hasattr(self, method):
                        self.log.error("The CsmakeModule '%s' doesn't have a method called '%s' for pick entry '%s'", self.__class__.__name__, method, pick)
                        continue
                    formatFiltered = getattr(self, method)(
                        options,
                        formatFiltered,
                        pickparts[1])

                    self.log.devdebug("Links after pick '%s': %s", pick, str(formatFiltered))

            self.log.devdebug("Final links: %s", str(formatFiltered))
            failOnEmpty = True
            if 'no-error' in options:
                failOnEmpty = options['no-error'] == 'False'
            if len(formatFiltered) == 0 and failOnEmpty:
                self.log.error("No files found")
                self.log.failed()
                return False
            else:
                self.log.warning("No files found. 'no-error' is not False")

            #Fetch each of the remaining pieces (TODO: in parallel)
            url = options['URL']
            if url[-1] != '/':
                url += '/'

            basepath = self.env.env['RESULTS']
            if 'local' in options:
                basepath = options['local']
                try:
                    os.makedirs(basepath)
                except OSError as e:
                    self.log.info("Attempt to create '%s': %s", basepath, str(e))
            for link in formatFiltered:
                urlfile = link[1]
                _, filename = os.path.split(link[1])
                _, landingName = os.path.split(link[-1])
                fullurl = urlparse.urljoin(url, urlfile)
                self.log.devdebug("Pulling URL: %s", fullurl)
                command = ['wget']
                if self.settings['debug']:
                    command.append('--debug')
                elif self.settings['verbose']:
                    command.append('--verbose')
                elif self.settings['quiet']:
                   command.append('--quiet')
                if not self.useProxy:
                   command.append('--no-proxy')
                command.extend(
                    ['--no-use-server-timestamps', '-O', os.path.join(basepath, landingName), fullurl ] )
                subprocess.check_call(
                    command,
                    stdout=self.log.out(),
                    stderr=self.log.err() )
                #getlink = urllib2.urlopen(fullurl)
                #with open(os.path.join(basepath, filename),'w') as localfile:
                #    r = getlink.read(self.READ_BUFFER_SIZE)
                #    while len(r) != 0:
                #        localfile.write(r)
                #        r = getlink.read(self.READ_BUFFER_SIZE)
                #    getlink.close()
        finally:
            #TODO: Fix the error handling
            pass
        self.log.passed()
        return formatFiltered
