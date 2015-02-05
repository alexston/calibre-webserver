#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre import prepare_string_for_xml
from calibre.gui2.tweak_book import current_container

DEFAULT_TEMPLATES = {
    'html':
'''\
<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <title>{TITLE}</title>
    </head>
    <body>
        %CURSOR%
    </body>
</html>
''',


    'css':
'''\
@charset utf-8;
/* Styles for {TITLE} */
%CURSOR%
''',

}

def template_for(syntax):
    mi = current_container().mi
    data = {
        'TITLE':mi.title,
        'AUTHOR': ' & '.join(mi.authors),
    }
    template = DEFAULT_TEMPLATES.get(syntax, '')
    return template.format(**{k:prepare_string_for_xml(v, True) for k, v in data.iteritems()})

