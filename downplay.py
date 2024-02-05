#! /usr/lib/python3

import sys
import os
import traceback
import argparse
import xml.etree.ElementTree as ET

from PySide import QtCore, QtGui
from PySide.QtCore import Qt


class ScriptEdit(QtGui.QTextEdit):

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

        self.setLineWrapMode(QtGui.QTextEdit.FixedPixelWidth)
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

        font = QtGui.QFont("Courier New",12,QtGui.QFont.Normal,False)
        self.document().setDefaultFont(font)
        
        text_option = QtGui.QTextOption()
        text_option.setAlignment(Qt.AlignLeft)
        text_option.setFlags(0)
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

    def create_action(self,label,shortcut=None,function=None):
        action = QtGui.QAction(label,self)
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

    def find_in_document(self,find_text,flags=0):
        status = self.find(find_text,flags)
        if status:
            self.setFocus()
        else:
            QtGui.QMessageBox.information(
                self,"Search term not found",
                "No more instances of the search term %r "
                "found in document" % find_text)

    def replace_in_document(self,find_text,replace_text,flags=0):
        cursor = self.textCursor()
        selected_text = cursor.selectedText()
        if flags & QtGui.QTextDocument.FindCaseSensitively:
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
        answer = QtGui.QMessageBox.warning(
            self,"Discard current document?",
            "The current document contains unsaved changes.",
            QtGui.QMessageBox.Discard | QtGui.QMessageBox.Cancel)
        return answer == QtGui.QMessageBox.Discard

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
        new_filename,filter = QtGui.QFileDialog.getOpenFileName(
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
            QtGui.QMessageBox.warning(
                self,"Invalid XML",
                "The file %s contained invalid XML" % basename)
            return
        except Exception as exc:
            if isinstance(exc,IOError) and exc.errno == 2:
                QtGui.QMessageBox.warning(
                    self,"File not found",
                    "File %s not found" % basename)                
            else:
                QtGui.QMessageBox.warning(
                    self,"File error",
                    "Error reading file %s; runtime returned the "
                    "following error message:\n%s"
                    % (basename, traceback.format_exc()))
            return
        xdownplay = doc.getroot()
        if xdownplay.tag != "downplay" \
           or xdownplay.attrib.get("format") is None:
            QtGui.QMessageBox.warning(
                self,"File format error",
                "File %s not a Downplay file" % basename)
            return
        format = xdownplay.attrib["format"]
        if format != "1.0":
            QtGui.QMessageBox.warning(
                self,"File format error",
                "File %s has unsupported Downplay format %s"
                % (basename, format))
            return
        for xp in xdownplay:
            if xp.tag != "p" or len(xp) != 0 \
               or xp.attrib.get("style","ACTION") not in self.MARGINS:
                QtGui.QMessageBox.warning(
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
        new_filename,filter = QtGui.QFileDialog.getSaveFileName(
            self,"Save buffer as Downplay file...",start_dirname,
            "Downplay files (*.dply);;All files (*)")
        if filter == "Downplay files (*.dply)":
            stub,ext = os.path.splitext(new_filename)
            if ext == "":
                new_filename = "%s.dply" % stub
        if new_filename != "":
            self.save_to_filename(new_filename)
            self.document().setModified(False)

    def save_a_copy(self):
        if self.last_dirname is not None:
            start_dirname = self.last_dirname
        else:
            start_dirname = os.getcwd()
        new_filename,filter = QtGui.QFileDialog.getSaveFileName(
            self,"Save copy of buffer as Downplay file...",start_dirname,
            "Downplay files (*.dply);;All files (*)")
        if filter == "Downplay files (*.dply)":
            stub,ext = os.path.splitext(new_filename)
            if ext == "":
                new_filename = "%s.dply" % stub
        if new_filename != "":
            self.save_to_filename(new_filename,is_copy=True)

    def save_to_filename(self,filename,is_copy=False):
        filename = os.path.normpath(os.path.abspath(filename))
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
        if warnings:
            message = [ "The following potential problems were encountered:" ]
            message.extend(sorted(warnings))
            message.append("Save anyway?")
            response = QtGui.QMessageBox.warning(
                self,"Problem with document","\n".join(message),
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            if response == QtGui.QMessageBox.No:
                return
        try:
            with open(filename,"wb") as flo:
                ET.ElementTree(xdownplay).write(flo,"utf-8",True)
        except Exception:
            QtGui.QMessageBox.warning(
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

    def emit_status_change(self):
        self.statusChanged.emit(self.get_status_line())

    def get_status_line(self):
        return "%s%s        %s" % (
            (os.path.basename(self.current_filename)
             if self.current_filename is not None else "Untitled"), 
            ("*" if self.document().isModified() else ""),
            self.get_margin_type())


class SearchDialog(QtGui.QDockWidget):

    findRequested = QtCore.Signal(str,int)
    replaceRequested = QtCore.Signal(str,str,int)

    def __init__(self,parent=None):
        super().__init__(parent)

        self.setFeatures(QtGui.QDockWidget.DockWidgetClosable
                         | QtGui.QDockWidget.DockWidgetMovable
                         | QtGui.QDockWidget.DockWidgetFloatable)

        self.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)

        self.setFloating(True)

        base = QtGui.QWidget()
        self.setWidget(base)

        layout = QtGui.QGridLayout()
        base.setLayout(layout)

        self.find_entry = QtGui.QLineEdit()
        layout.addWidget(self.find_entry,0,0,Qt.AlignLeft)

        self.replace_entry = QtGui.QLineEdit()
        layout.addWidget(self.replace_entry,1,0,Qt.AlignLeft)

        self.find_button = QtGui.QPushButton("Find")
        layout.addWidget(self.find_button,0,1,Qt.AlignRight)

        self.replace_button = QtGui.QPushButton("Replace")
        layout.addWidget(self.replace_button,1,1,Qt.AlignRight)

        self.backward_checkbox = QtGui.QCheckBox("Search backwards")
        layout.addWidget(self.backward_checkbox,0,2,Qt.AlignLeft)

        self.case_checkbox = QtGui.QCheckBox("Case sensitive")
        layout.addWidget(self.case_checkbox,0,3,Qt.AlignLeft)

        self.whole_checkbox = QtGui.QCheckBox("Whole words only")
        layout.addWidget(self.whole_checkbox,0,4,Qt.AlignLeft)

        self.find_button.clicked.connect(self.find)
        self.replace_button.clicked.connect(self.replace)

    def flags(self):
        flags = 0
        if self.backward_checkbox.isChecked():
            flags |= QtGui.QTextDocument.FindBackward
        if self.case_checkbox.isChecked():
            flags |= QtGui.QTextDocument.FindCaseSensitively
        if self.whole_checkbox.isChecked():
            flags |= QtGui.QTextDocument.FindWholeWords
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
        if isinstance(menu_item_def,QtGui.QAction):
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
            
    
def main():
    ap = argparse.ArgumentParser(description='Invoke Downplay')
    ap.add_argument("filename",default=None,nargs='?',help='File to open')
    args = ap.parse_args()

    app = QtGui.QApplication([])
    
    script_edit = ScriptEdit()
    if args.filename is not None:
        script_edit.open_filename(args.filename)

    search_dialog = SearchDialog()
    search_dialog.findRequested.connect(script_edit.find_in_document)
    search_dialog.replaceRequested.connect(script_edit.replace_in_document)

    win = QtGui.QMainWindow()

    win.setCentralWidget(script_edit)

    menu_bar_def = [
        ( '&File', None, (
            script_edit.new_action,
            script_edit.open_action,
            script_edit.save_action,
            script_edit.save_as_action,
            script_edit.save_a_copy_action,
            "-",
            #( "&Export...", None ),
            #"-",
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


if __name__ == '__main__':
    main()
