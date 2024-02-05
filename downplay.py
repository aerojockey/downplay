#! /usr/bin/python3

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import os
import re
import traceback
import argparse
import xml.etree.ElementTree as ET

from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib import pagesizes, units
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False



def format_paragraph(text,indent,width):
    lines = []
    line = []
    c = 0
    for word in text.split():
        if c + len(line) + len(word) > width:

            b = len(word)
            while True:
                i = word.rfind('-',0,b)
                if i == -1:
                    break
                if c + len(line) + i + 1 <= width:
                    line.append(word[:i+1])
                    lines.append(" "*indent + " ".join(line))
                    line = []
                    c = 0
                    word = word[i+1:]
                    b = len(word)
                    if b <= width:
                        break
                else:
                    b = i
            if c != 0:
                lines.append(" "*indent + " ".join(line))
                line = []
                c = 0
        line.append(word)
        c += len(word)
    if len(line) != 0:
        lines.append(" "*indent + " ".join(line))
    return lines

def format(xdownplay):
    text = []
    for xp in xdownplay.findall('p'):
        if xp.text in (None,""):
            text.append("")
            continue
        style = xp.attrib["style"]
        if style == "ACTION":
            text.extend(format_paragraph(xp.text,0,60))
        elif style == "DIALOGUE":
            text.extend(format_paragraph(xp.text,10,30))
        elif style == "NAME":
            text.extend(format_paragraph(xp.text,20,20))
        elif style == "PARENTHETICAL":
            text.extend(format_paragraph(xp.text,15,25))
        elif style == "TRANSITION":
            text.extend(format_paragraph(xp.text,45,15))
        else:
            assert False
    text.append("")
    return "\n".join(text)

def paginate(xdownplay):
    def page_break():
        nonlocal line_number, page_number, eat_space
        while line_number < 60:
            text.append("")
            line_number += 1
        line_number = 0
        page_number += 1
        eat_space = True
    def add_line(line):
        nonlocal line_number, page_number, eat_space
        if eat_space and line in (None,""):
            eat_space = False
            return
        while line_number < 4:
            if line_number == 2 and page_number > 1:
                text.append("%*s%d." % (55,"",page_number))
            else:
                text.append("")
            line_number += 1
        text.append(line)
        line_number += 1
        if line_number >= 56:
            page_break()
        else:
            eat_space = False
    def add_lines(lines):
        for line in lines:
            add_line(line)
    def add_clump(reserve=0):
        if len(clump) == 0:
            return
        if len(clump) > 10:  # don't even try
            add_lines(clump)
            clump.clear()
            return
        if line_number + len(clump) + reserve > 56:
            page_break()
        add_lines(clump)
        clump.clear()
    text = []
    line_number = 0
    page_number = 1
    eat_space = False
    clump = []
    for xp in xdownplay.findall('p'):
        if xp.text in (None,""):
            add_clump()
            add_line("")
            continue
        style = xp.attrib["style"]
        if style == "ACTION":
            add_clump()
            add_lines(format_paragraph(xp.text,0,60))
        elif style == "DIALOGUE":
            paragraph = format_paragraph(xp.text,10,30)
            add_clump(max(2,len(paragraph)))
            while line_number + len(paragraph) > 56:
                n_balance = 55-line_number
                balance,paragraph = paragraph[:n_balance],paragraph[n_balance:]
                add_lines(balance)
                add_lines(("%*s(MORE)" % (20,""),))
            add_lines(paragraph)
        elif style == "NAME":
            clump.extend(format_paragraph(xp.text,20,20))
        elif style == "PARENTHETICAL":
            clump.extend(format_paragraph(xp.text,15,25))
        elif style == "TRANSITION":
            add_clump()
            add_lines(format_paragraph(xp.text,45,15))
        else:
            assert False
    add_clump()
    page_break()
    return "\n".join(text)

def export_as_text(xdownplay,txt_filename,*,paginated=True):
    if paginated:
        text = paginate(xdownplay)
    else:
        text = format(xdownplay)
    with open(txt_filename,"w",encoding='utf-8') as flo:
        flo.write(text)

def export_as_pdf(xdownplay,pdf_filename):
    text = paginate(xdownplay)
    pdf = canvas.Canvas(pdf_filename,pagesize=pagesizes.letter)
    font_set = False
    line_number = 0
    for line in text.split("\n"):
        if line != "":
            if not font_set:
                pdf.setFont("Courier",12)
                font_set = True
            pdf.drawString(1.7*units.inch,10.5*units.inch-line_number*12,line)
        line_number += 1
        if line_number >= 60:
            line_number = 0
            pdf.showPage()
            font_set = False
    pdf.save()










class ScriptEdit(QtWidgets.QTextEdit):

    MARGINS = {
        'ACTION': (0,0),
        'DIALOGUE': (100,200),
        'PARENTHETICAL': (150,200),
        'NAME': (200,200),
        'TRANSITION': (450,0),
        }

    REV_MARGINS = { v[0]:k for (k,v) in MARGINS.items() }

    statusChanged = QtCore.Signal(str)

    def __init__(self,parent=None):
        super().__init__(parent)

        self.changed_timer = QtCore.QTimer(self)
        self.changed_timer.setInterval(0)
        self.changed_timer.setSingleShot(True)
        self.changed_timer.timeout.connect(self.emit_status_change)

        self.setLineWrapMode(QtWidgets.QTextEdit.FixedPixelWidth)
        self.setLineWrapColumnOrWidth(600)

        self.setAcceptRichText(False)

        self.new_action = self.create_action(
            "&New", None, self.new)
        self.open_action = self.create_action(
            "&Open...", Qt.Key_O | Qt.CTRL, self.open)
        self.save_action = self.create_action(
            "&Save", Qt.Key_S | Qt.CTRL, self.save)
        self.save_as_action = self.create_action(
            "Save &As...", None, self.save_as)
        self.save_a_copy_action = self.create_action(
            "Save a &Copy...", None, self.save_a_copy)
        self.export_as_text_action = self.create_action(
            "Export as continuous text...", None, self.export_as_text)
        self.export_as_pages_action = self.create_action(
            "Export as paginated text...", None, self.export_as_pages)
        self.export_as_pdf_action = self.create_action(
            "Export as PDF...", None, self.export_as_pdf,
            enabled=HAS_REPORTLAB)
        self.print_to_console_action = self.create_action(
            "Print to console", None, self.print_to_console)

        self.undo_action = self.create_action(
            "&Undo", Qt.Key_Z | Qt.CTRL, self.undo)
        self.redo_action = self.create_action(
            "&Redo", Qt.Key_Y | Qt.CTRL, self.redo)
        self.copy_action = self.create_action(
            "&Copy", Qt.Key_X | Qt.CTRL, self.copy)
        self.cut_action = self.create_action(
            "Cu&t", Qt.Key_C | Qt.CTRL, self.cut)
        self.paste_action = self.create_action(
            "&Paste", Qt.Key_V | Qt.CTRL, self.paste)

        self.action_style_action = self.create_action(
            "&Action Style", Qt.Key_F5 | Qt.NoModifier,
            lambda: self.set_margin_type('ACTION'))
        self.dialogue_style_action = self.create_action(
            "&Dialogue Style", Qt.Key_F6 | Qt.NoModifier,
            lambda: self.set_margin_type('DIALOGUE'))
        self.parenthetical_style_action = self.create_action(
            "&Parenthetical Style", Qt.Key_F7 | Qt.NoModifier,
            lambda: self.set_margin_type('PARENTHETICAL'))
        self.name_style_action = self.create_action(
            "&Name Style", Qt.Key_F8 | Qt.NoModifier,
            lambda: self.set_margin_type('NAME'))
        self.transition_style_action = self.create_action(
            "&Transition Style", Qt.Key_F9 | Qt.NoModifier,
            lambda: self.set_margin_type('TRANSITION'))
        self.cycle_styles_action = self.create_action(
            "Cycle &Styles", Qt.Key_Tab | Qt.NoModifier,
            self.cycle_margin)

        self.estimate_pages_action = self.create_action(
            "Estimate number of &Pages", None, self.estimate_pages)

        font = QtGui.QFont('Courier',12,QtGui.QFont.Normal,False)

        self.document().setDefaultFont(font)

        text_option = QtGui.QTextOption()
        text_option.setAlignment(Qt.AlignLeft)
        text_option.setFlags(QtGui.QTextOption.Flags()) # 0
        text_option.setTabArray([])
        text_option.setTextDirection(Qt.LeftToRight)
        text_option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(text_option)

        self.last_dirname = None
        self.current_filename = None

        self.enable_signals()

        self.new()

    def keyPressEvent(self,event):
        if event.key() == Qt.Key_Tab:
            self.cycle_margin()
        else:
            super().keyPressEvent(event)

    def enable_signals(self):
        QtCore.QObject.connect(self.document(),
                               QtCore.SIGNAL("modificationChanged(bool)"),
                               self.changed_timer,
                               QtCore.SLOT("start()"))
        QtCore.QObject.connect(self,
                               QtCore.SIGNAL("cursorPositionChanged()"),
                               self.changed_timer,
                               QtCore.SLOT("start()"))

    def disable_signals(self):
        QtCore.QObject.disconnect(self.document(),
                                  QtCore.SIGNAL("modificationChanged(bool)"),
                                  self.changed_timer,
                                  QtCore.SLOT("start()"))
        QtCore.QObject.disconnect(self,
                                  QtCore.SIGNAL("cursorPositionChanged()"),
                                  self.changed_timer,
                                  QtCore.SLOT("start()"))

    def create_action(self,label,shortcut=None,function=None,enabled=True):
        action = QtWidgets.QAction(label,self)
        action.setEnabled(enabled)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if function is not None:
            action.triggered.connect(function)
        return action

    def set_margin_type(self,margin_type):
        left_margin,right_margin = self.MARGINS[margin_type]
        cursor = self.textCursor()
        block_format = cursor.blockFormat()
        block_format.setLeftMargin(left_margin)
        block_format.setRightMargin(right_margin)
        cursor.setBlockFormat(block_format)
        self.changed_timer.start()

    def get_margin_type(self):
        cursor = self.textCursor()
        block_format = cursor.blockFormat()
        left_margin = block_format.leftMargin()
        return self.REV_MARGINS.get(left_margin,'ACTION')

    def cycle_margin(self):
        margin_type = self.get_margin_type()
        if margin_type == 'ACTION':
            self.set_margin_type('NAME')
        elif margin_type == 'NAME':
            self.set_margin_type('DIALOGUE')
        else:
            self.set_margin_type('ACTION')

    def find_in_document(self,find_text,flags=QtGui.QTextDocument.FindFlag()):
        status = self.find(find_text,flags)
        if status:
            self.setFocus()
        else:
            QtWidgets.QMessageBox.information(
                self,"Search term not found",
                "No more instances of the search term %r "
                "found in document" % find_text)

    def replace_in_document(self,find_text,replace_text,flags=QtGui.QTextDocument.FindFlag()):
        cursor = self.textCursor()
        selected_text = cursor.selectedText()
        if flags & QtWidgets.QTextDocument.FindCaseSensitively:
            lhs = find_text
            rhs = selected_text
        else:
            lhs = find_text.lower()
            rhs = selected_text.lower()
        if lhs == rhs:
            cursor.insertText(replace_text)
        self.find_in_document(find_text,flags)

    def ok_to_discard(self):
        if not self.document().isModified():
            return True
        answer = QtWidgets.QMessageBox.warning(
            self,"Discard current document?",
            "The current document contains unsaved changes.",
            QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel)
        return answer == QtWidgets.QMessageBox.Discard

    def new(self):
        if not self.ok_to_discard():
            return
        self.document().clear()
        self.current_filename = None
        self.set_margin_type('ACTION')
        self.document().setModified(False)

    def open(self):
        if not self.ok_to_discard():
            return
        if self.last_dirname is not None:
            start_dirname = self.last_dirname
        else:
            start_dirname = os.getcwd()
        new_filename,filter = QtWidgets.QFileDialog.getOpenFileName(
            self,"Open Downplay file...",start_dirname,
            "Downplay files (*.dply);;All files (*)")
        if new_filename != "":
            self.open_filename(new_filename)

    def open_filename(self,filename):
        filename = os.path.normpath(os.path.abspath(filename))
        basename = os.path.basename(filename)
        try:
            with open(filename,"rb") as flo:
                doc = ET.parse(flo)
        except ET.ParseError:
            QtWidgets.QMessageBox.warning(
                self,"Invalid XML",
                "The file %s contained invalid XML" % basename)
            return
        except Exception as exc:
            if isinstance(exc,IOError) and exc.errno == 2:
                QtWidgets.QMessageBox.warning(
                    self,"File not found",
                    "File %s not found" % basename)
            else:
                QtWidgets.QMessageBox.warning(
                    self,"File error",
                    "Error reading file %s; runtime returned the "
                    "following error message:\n%s"
                    % (basename, traceback.format_exc()))
            return
        xdownplay = doc.getroot()
        if xdownplay.tag != "downplay" \
           or xdownplay.attrib.get("format") is None:
            QtWidgets.QMessageBox.warning(
                self,"File format error",
                "File %s not a Downplay file" % basename)
            return
        format = xdownplay.attrib["format"]
        if format != "1.0":
            QtWidgets.QMessageBox.warning(
                self,"File format error",
                "File %s has unsupported Downplay format %s"
                % (basename, format))
            return
        for xp in xdownplay:
            if xp.tag != "p" or len(xp) != 0 \
               or xp.attrib.get("style","ACTION") not in self.MARGINS:
                QtWidgets.QMessageBox.warning(
                    self,"File format error",
                    "File %s has unsupported Downplay has invalid elements"
                    % (basename, format))
                return
        self.disable_signals()
        try:
            cursor = self.textCursor()
            first = True
            for xp in xdownplay:
                margin_type = xp.attrib.get("style","ACTION")
                if first:
                    self.clear()
                    first = False
                else:
                    cursor.insertBlock()
                self.set_margin_type(margin_type)
                cursor.insertText(xp.text)
            self.moveCursor(QtGui.QTextCursor.Start)
        finally:
            self.enable_signals()
        self.current_filename = filename
        self.last_dirname = os.path.dirname(filename)
        self.document().setModified(False)
        self.changed_timer.start()

    def extract_xml(self):
        xdownplay = ET.Element("downplay")
        xdownplay.attrib["format"] = "1.0"
        xdownplay.text = "\n  "
        warnings = set()
        for tfi in self.document().rootFrame():
            text_block = tfi.currentBlock()
            if not text_block.isValid():
                warnings.add("Unexpectedly encountered a frame "
                             "in the document; skipping")
            else:
                block_format = text_block.blockFormat()
                left_margin = block_format.leftMargin()
                margin_type = self.REV_MARGINS.get(left_margin,'ACTION')
                xp = ET.SubElement(xdownplay,"p",style=margin_type)
                xp.text = text_block.text()
            xp.tail = "\n  "
        xp.tail = "\n"
        return xdownplay, warnings

    def save(self):
        if self.current_filename is not None:
            self.save_to_filename(self.current_filename)
        else:
            self.save_as()

    def save_as(self):
        if self.last_dirname is not None:
            start_dirname = self.last_dirname
        else:
            start_dirname = os.getcwd()
        new_filename,filter = QtWidgets.QFileDialog.getSaveFileName(
            self,"Save buffer as Downplay file...",start_dirname,
            "Downplay files (*.dply);;All files (*)")
        if new_filename != "":
            if filter == "Downplay files (*.dply)":
                stub,ext = os.path.splitext(new_filename)
                if ext == "":
                    new_filename = "%s.dply" % stub
            self.save_to_filename(new_filename)
            self.document().setModified(False)

    def save_a_copy(self):
        if self.last_dirname is not None:
            start_dirname = self.last_dirname
        else:
            start_dirname = os.getcwd()
        new_filename,filter = QtWidgets.QFileDialog.getSaveFileName(
            self,"Save copy of buffer as Downplay file...",start_dirname,
            "Downplay files (*.dply);;All files (*)")
        if filter == "Downplay files (*.dply)":
            stub,ext = os.path.splitext(new_filename)
            if ext == "":
                new_filename = "%s.dply" % stub
        if new_filename != "":
            self.save_to_filename(new_filename,is_copy=True)

    def save_to_filename(self,filename,is_copy=False):
        xdownplay, warnings = self.extract_xml()
        if warnings:
            message = [ "The following potential problems were encountered:" ]
            message.extend(sorted(warnings))
            message.append("Save anyway?")
            response = QtWidgets.QMessageBox.warning(
                self,"Problem with document","\n".join(message),
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if response == QtWidgets.QMessageBox.No:
                return
        filename = os.path.normpath(os.path.abspath(filename))
        try:
            with open(filename,"wb") as flo:
                ET.ElementTree(xdownplay).write(flo,"utf-8",True)
        except Exception:
            QtWidgets.QMessageBox.warning(
                self,"File error",
                "Error writing file %s; runtime returned the "
                "following error message:\n%s"
                % (os.path.basename(filename), traceback.format_exc()))
            return
        if not is_copy:
            self.current_filename = filename
            self.last_dirname = os.path.dirname(filename)
            self.document().setModified(False)
            self.changed_timer.start()

    def export_as_text(self):
        self.export_as_text_common(False)

    def export_as_pages(self):
        self.export_as_text_common(True)

    def export_as_text_common(self,paginated):
        if self.last_dirname is not None:
            start_dirname = self.last_dirname
        else:
            start_dirname = os.getcwd()
        if self.current_filename is not None:
            stub,ext = os.path.splitext(self.current_filename)
            start_pathname = os.path.join(start_dirname,stub+".txt")
        else:
            start_pathname = start_dirname
        if paginated:
            how = "paginated"
        else:
            how = "continuous"
        new_filename,filter = QtWidgets.QFileDialog.getSaveFileName(
            self,"Export buffer as %s text file..." % how,start_pathname,
            "Text files (*.txt);;All files (*)")
        if new_filename != "":
            if filter == "Text files (*.txt)":
                stub,ext = os.path.splitext(new_filename)
                if ext == "":
                    new_filename = "%s.txt" % stub
            xdownplay,warnings = self.extract_xml()
            export_as_text(xdownplay,new_filename,paginated=paginated)

    def export_as_pdf(self):
        if self.last_dirname is not None:
            start_dirname = self.last_dirname
        else:
            start_dirname = os.getcwd()
        if self.current_filename is not None:
            stub,ext = os.path.splitext(self.current_filename)
            start_pathname = os.path.join(start_dirname,stub+".pdf")
        else:
            start_pathname = start_dirname
        new_filename,filter = QtWidgets.QFileDialog.getSaveFileName(
            self,"Export buffer as PDF file...",start_pathname,
            "PDF files (*.pdf);;All files (*)")
        if new_filename != "":
            if filter == "PDF files (*.pdf)":
                stub,ext = os.path.splitext(new_filename)
                if ext == "":
                    new_filename = "%s.pdf" % stub
            xdownplay,warnings = self.extract_xml()
            export_as_pdf(xdownplay,new_filename)

    def print_to_console(self):
        print("-"*79)
        xdownplay,warnings = self.extract_xml()
        print(self.format(xdownplay))
        print("-"*79)

    def estimate_pages(self):
        lines_per_page = 52
        xdownplay,warnings = self.extract_xml()
        text = self.format(xdownplay)
        n_lines = text.count("\n")
        n_pages = n_lines / 52
        QtWidgets.QMessageBox.information(
            self,"Page count estimate",
            "Page count estimated at %g, based on %g lines per page."
            % (n_pages, lines_per_page))

    def emit_status_change(self):
        self.statusChanged.emit(self.get_status_line())

    def get_status_line(self):
        return "%s%s        %s" % (
            (os.path.basename(self.current_filename)
             if self.current_filename is not None else "Untitled"),
            ("*" if self.document().isModified() else ""),
            self.get_margin_type())


    _keepalive = []

    def createMimeDataFromSelection(self):
        cursor = self.textCursor()
        text = cursor.selectedText().replace('\u2029','\n')
        downplay_data = cursor.selection().toHtml().encode('utf-8')
        mime_data = QtCore.QMimeData()
        mime_data.setText(text)
        mime_data.setData('application/x-downplay',downplay_data)

        # Workaround: ownership passes to caller, so must do this to
        # prevent python from garbage collecting it.  Causes segfault on
        # exit.  Was fixed in later PySide so don't worry too much.
        self._keepalive.append(mime_data)

        return mime_data

    def canInsertFromMimeData(self,mime_data):
        return mime_data.hasFormat('application/x-downplay') or mime_data.hasFormat('text/plain')

    def insertFromMimeData(self,mime_data):
        if mime_data.hasFormat('application/x-downplay'):
            downplay_data = str(mime_data.data('application/x-downplay'),'utf-8')
            cursor = self.textCursor()
            cursor.insertHtml(downplay_data)
        elif mime_data.hasFormat('text/plain'):
            text = mime_data.text().replace('\n','\u2029')
            cursor = self.textCursor()
            cursor.insertText(text)



class SearchDialog(QtWidgets.QDockWidget):

    findRequested = QtCore.Signal(str,int)
    replaceRequested = QtCore.Signal(str,str,int)

    def __init__(self,parent=None):
        super().__init__(parent)

        self.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable
                         | QtWidgets.QDockWidget.DockWidgetMovable
                         | QtWidgets.QDockWidget.DockWidgetFloatable)

        self.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)

        self.setFloating(True)

        base = QtWidgets.QWidget()
        self.setWidget(base)

        layout = QtWidgets.QGridLayout()
        base.setLayout(layout)

        self.find_entry = QtWidgets.QLineEdit()
        layout.addWidget(self.find_entry,0,0,Qt.AlignLeft)

        self.replace_entry = QtWidgets.QLineEdit()
        layout.addWidget(self.replace_entry,1,0,Qt.AlignLeft)

        self.find_button = QtWidgets.QPushButton("Find")
        layout.addWidget(self.find_button,0,1,Qt.AlignRight)

        self.replace_button = QtWidgets.QPushButton("Replace")
        layout.addWidget(self.replace_button,1,1,Qt.AlignRight)

        self.backward_checkbox = QtWidgets.QCheckBox("Search backwards")
        layout.addWidget(self.backward_checkbox,0,2,Qt.AlignLeft)

        self.case_checkbox = QtWidgets.QCheckBox("Case sensitive")
        layout.addWidget(self.case_checkbox,0,3,Qt.AlignLeft)

        self.whole_checkbox = QtWidgets.QCheckBox("Whole words only")
        layout.addWidget(self.whole_checkbox,0,4,Qt.AlignLeft)

        self.find_button.clicked.connect(self.find)
        self.replace_button.clicked.connect(self.replace)

    def flags(self):
        flags = 0
        if self.backward_checkbox.isChecked():
            flags |= QtWidgets.QTextDocument.FindBackward
        if self.case_checkbox.isChecked():
            flags |= QtWidgets.QTextDocument.FindCaseSensitively
        if self.whole_checkbox.isChecked():
            flags |= QtWidgets.QTextDocument.FindWholeWords
        return flags

    def find(self):
        find_text = self.find_entry.text()
        if find_text == "":
            return
        flags = self.flags()
        self.findRequested.emit(find_text,flags)

    def replace(self):
        find_text = self.find_entry.text()
        if find_text == "":
            return
        replace_text = self.replace_entry.text()
        flags = self.flags()
        self.replaceRequested.emit(find_text,replace_text,flags)

    def activate(self):
        self.show()
        self.find_entry.setFocus()


def populate_menu(menu,menu_def):
    def def_error():
        raise ValueError("invalid menu item definition %r" % (menu_item_def,))
    for menu_item_def in menu_def:
        if isinstance(menu_item_def,QtWidgets.QAction):
            menu.addAction(menu_item_def)
        elif isinstance(menu_item_def,tuple):
            name,shortcut,data = menu_item_def
            if not isinstance(name,str):
                def_error()
            if data is None:
                action = menu.addAction(name)
            elif isinstance(data,tuple):
                action = menu.addMenu(name)
                populate_menu(action,data)
            else:
                action = menu.addAction(name)
                action.triggered.connect(data)
            if shortcut is not None:
                action.setShortcut(shortcut)
        elif menu_item_def == "-":
            menu.addSeparator()
        else:
            def_error()


def gui(filename=None):
    app = QtWidgets.QApplication([])

    script_edit = ScriptEdit()
    if filename is not None:
        script_edit.open_filename(filename)

    search_dialog = SearchDialog()
    search_dialog.findRequested.connect(script_edit.find_in_document)
    search_dialog.replaceRequested.connect(script_edit.replace_in_document)

    win = QtWidgets.QMainWindow()

    win.setCentralWidget(script_edit)

    menu_bar_def = [
        ( '&File', None, (
            script_edit.new_action,
            script_edit.open_action,
            script_edit.save_action,
            script_edit.save_as_action,
            script_edit.save_a_copy_action,
            "-",
            script_edit.export_as_text_action,
            script_edit.export_as_pages_action,
            script_edit.export_as_pdf_action,
            script_edit.print_to_console_action,
            "-",
            ( "&Quit", Qt.Key_F4 | Qt.ALT, sys.exit ),
            ),
        ),
        ( '&Edit', None, (
            script_edit.undo_action,
            script_edit.redo_action,
            "-",
            script_edit.cut_action,
            script_edit.copy_action,
            script_edit.paste_action,
            "-",
            ( "&Find and Replace...", Qt.Key_F | Qt.CTRL,
              search_dialog.activate ),
            ),
        ),
        ( '&Styles', None, (
            script_edit.cycle_styles_action,
            "-",
            script_edit.action_style_action,
            script_edit.dialogue_style_action,
            script_edit.parenthetical_style_action,
            script_edit.name_style_action,
            script_edit.transition_style_action,
            ),
        ),
        ( '&Info', None, (
            script_edit.estimate_pages_action,
            ),
        ),
        ]

    menu_bar = win.menuBar()
    populate_menu(menu_bar,menu_bar_def)

    status_bar = win.statusBar()
    status_bar.showMessage(script_edit.get_status_line())
    script_edit.statusChanged.connect(status_bar.showMessage)

    win.addDockWidget(Qt.BottomDockWidgetArea,search_dialog)
    search_dialog.hide()

    win.resize(620,700)
    win.show()

    app.exec_()


def convert(downplay_filenames,output_filename):
    xdownplay = ET.Element('downplay',format="1.0")
    for i,filename in enumerate(downplay_filenames):
        if not filename.endswith('.dply'):
            raise RuntimeError('input filenames must all be downplay files')
        if i != 0:
            ET.SubElement(xdownplay,'p',style='ACTION')
        xsdp = ET.parse(filename).getroot()
        xdownplay.extend(xsdp[:])
    if output_filename.endswith('.pdf'):
        if not HAS_REPORTLAB:
            raise RuntimeError("can't import reportlab")
        export_as_pdf(xdownplay,output_filename)
    elif output_filename.endswith('.txt'):
        export_as_text(xdownplay,output_filename)
    else:
        raise RuntimeError('out filenames must all be text or PDF')


def main():
    ap = argparse.ArgumentParser(description='Invoke Downplay')
    ap.add_argument("filename",default=None,nargs='?',help='File to open')
    ap.add_argument("--convert",default=None,nargs='*',metavar="FILENAME",help="Convert a downplay flies to a PDF/TXT file")
    args = ap.parse_args()
    if args.convert is not None:
        convert(args.convert[:-1],args.convert[-1])
    else:
        gui(args.filename)


if __name__ == '__main__':
    main()
