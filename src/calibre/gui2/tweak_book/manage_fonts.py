#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys

from PyQt4.Qt import (
    QSplitter, QVBoxLayout, QTableView, QWidget, QLabel, QAbstractTableModel,
    Qt, QApplication, QTimer, QPushButton, pyqtSignal, QFormLayout, QLineEdit,
    QIcon, QSize)

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.fonts import font_family_data, change_font
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import current_container, set_current_container
from calibre.gui2.tweak_book.widgets import Dialog, BusyCursor
from calibre.utils.icu import primary_sort_key as sort_key
from calibre.utils.fonts.scanner import font_scanner, NoFonts

class AllFonts(QAbstractTableModel):

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.items = []
        self.font_data = {}
        self.sorted_on = ('name', True)

    def rowCount(self, parent=None):
        return len(self.items)

    def columnCount(self, parent=None):
        return 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _('Font family') if section == 1 else _('Embedded')
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def build(self):
        with BusyCursor():
            self.beginResetModel()
            self.font_data = font_family_data(current_container())
            self.do_sort()
            self.endResetModel()

    def do_sort(self):
        reverse = not self.sorted_on[1]
        self.items = sorted(self.font_data.iterkeys(), key=sort_key, reverse=reverse)
        if self.sorted_on[0] != 'name':
            self.items.sort(key=self.font_data.get, reverse=reverse)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row, col = index.row(), index.column()
            try:
                name = self.items[row]
                embedded = '✓ ' if self.font_data[name] else ''
            except (IndexError, KeyError):
                return
            return name if col == 1 else embedded
        if role == Qt.TextAlignmentRole:
            col = index.column()
            if col == 0:
                return Qt.AlignHCenter

    def sort(self, col, order=Qt.AscendingOrder):
        sorted_on = (('name' if col == 1 else 'embedded'), order == Qt.AscendingOrder)
        if sorted_on != self.sorted_on:
            self.sorted_on = sorted_on
            self.beginResetModel()
            self.do_sort()
            self.endResetModel()

    def data_for_indices(self, indices):
        ans = {}
        for idx in indices:
            try:
                name = self.items[idx.row()]
                ans[name] = self.font_data[name]
            except (IndexError, KeyError):
                pass
        return ans

class ChangeFontFamily(Dialog):

    def __init__(self, old_family, embedded_families, parent=None):
        self.old_family = old_family
        self.local_families = {icu_lower(f) for f in font_scanner.find_font_families()} | {
            icu_lower(f) for f in embedded_families}
        Dialog.__init__(self, _('Change font'), 'change-font-family', parent=parent)
        self.setMinimumWidth(300)
        self.resize(self.sizeHint())

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.setLayout(l)
        self.la = la = QLabel(ngettext(
            'Change the font %s to:', 'Change the fonts %s to:',
            self.old_family.count(',')+1) % self.old_family)
        la.setWordWrap(True)
        l.addRow(la)
        self._family = f = QLineEdit(self)
        l.addRow(_('&New font:'), f)
        f.textChanged.connect(self.updated_family)
        self.embed_status = e = QLabel('\xa0')
        l.addRow(e)
        l.addRow(self.bb)

    @property
    def family(self):
        return unicode(self._family.text())

    @property
    def normalized_family(self):
        ans = self.family
        try:
            ans = font_scanner.fonts_for_family(ans)[0]['font-family']
        except (NoFonts, IndexError, KeyError):
            pass
        if icu_lower(ans) == 'sansserif':
            ans = 'sans-serif'
        return ans

    def updated_family(self):
        family = self.family
        found = icu_lower(family) in self.local_families
        t = _('The font <i>%s</i> <b>exists</b> on your computer') if found else _(
            'The font <i>%s</i> <b>does not exist</b> on your computer')
        t = (t % family) if family else '\xa0'
        self.embed_status.setText(t)
        self.resize(self.sizeHint())


class ManageFonts(Dialog):

    container_changed = pyqtSignal()
    embed_all_fonts = pyqtSignal()
    subset_all_fonts = pyqtSignal()

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Manage Fonts'), 'manage-fonts', parent=parent)

    def setup_ui(self):
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.bb.clear()
        self.bb.addButton(self.bb.Close)
        self.splitter = s = QSplitter(self)
        l.addWidget(s), l.addWidget(self.bb)

        self.fonts_view = fv = QTableView(self)
        self.model = m = AllFonts(fv)
        fv.horizontalHeader().setStretchLastSection(True)
        fv.setModel(m)
        fv.setSortingEnabled(True)
        fv.setShowGrid(False)
        fv.setAlternatingRowColors(True)
        fv.setSelectionMode(fv.ExtendedSelection)
        fv.setSelectionBehavior(fv.SelectRows)
        fv.horizontalHeader().setSortIndicator(1, Qt.AscendingOrder)
        self.container = c = QWidget()
        l = c.l = QVBoxLayout(c)
        c.setLayout(l)
        s.addWidget(fv), s.addWidget(c)

        self.cb = b = QPushButton(_('&Change selected fonts'))
        b.setIcon(QIcon(I('auto_author_sort.png')))
        b.clicked.connect(self.change_fonts)
        l.addWidget(b)
        self.rb = b = QPushButton(_('&Remove selected fonts'))
        b.clicked.connect(self.remove_fonts)
        b.setIcon(QIcon(I('trash.png')))
        l.addWidget(b)
        self.eb = b = QPushButton(_('&Embed all fonts'))
        b.setIcon(QIcon(I('embed-fonts.png')))
        b.clicked.connect(self.embed_fonts)
        l.addWidget(b)
        self.sb = b = QPushButton(_('&Subset all fonts'))
        b.setIcon(QIcon(I('subset-fonts.png')))
        b.clicked.connect(self.subset_fonts)
        l.addWidget(b)
        self.refresh_button = b = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
        b.setToolTip(_('Rescan the book for fonts in case you have made changes'))
        b.setIcon(QIcon(I('view-refresh.png')))
        b.clicked.connect(self.refresh)

        self.la = la = QLabel('<p>' + _(
        ''' All the fonts declared in this book are shown to the left, along with whether they are embedded or not.
            You can remove or replace any selected font and also embed any declared fonts that are not already embedded.'''))
        la.setWordWrap(True)
        l.addWidget(la)

        l.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

    def sizeHint(self):
        return Dialog.sizeHint(self) + QSize(100, 50)

    def display(self):
        if not self.isVisible():
            self.show()
        self.raise_()
        QTimer.singleShot(0, self.model.build)

    def get_selected_data(self):
        ans = self.model.data_for_indices(list(self.fonts_view.selectedIndexes()))
        if not ans:
            error_dialog(self, _('No fonts selected'), _(
                'No fonts selected, you must first select some fonts in the left panel'), show=True)
        return ans

    def change_fonts(self):
        fonts = self.get_selected_data()
        if not fonts:
            return
        d = ChangeFontFamily(', '.join(fonts), {f for f, embedded in self.model.font_data.iteritems() if embedded}, self)
        if d.exec_() != d.Accepted:
            return
        changed = False
        new_family = d.normalized_family
        for font in fonts:
            changed |= change_font(current_container(), font, new_family)
        if changed:
            self.model.build()
            self.container_changed.emit()

    def remove_fonts(self):
        fonts = self.get_selected_data()
        if not fonts:
            return
        changed = False
        for font in fonts:
            changed |= change_font(current_container(), font)
        if changed:
            self.model.build()
            self.container_changed.emit()

    def embed_fonts(self):
        self.embed_all_fonts.emit()

    def subset_fonts(self):
        self.subset_all_fonts.emit()

    def refresh(self):
        self.model.build()

if __name__ == '__main__':
    app = QApplication([])
    c = get_container(sys.argv[-1], tweak_mode=True)
    set_current_container(c)
    d = ManageFonts()
    d.exec_()
    del app
