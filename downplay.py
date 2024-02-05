#! /usr/lib/python3

import sys
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

    
    def __init__(self,parent=None):
        super().__init__(parent)

        self.setLineWrapMode(QtGui.QTextEdit.FixedPixelWidth)
        self.setLineWrapColumnOrWidth(600)

        self.setAcceptRichText(False)
        
        self.copy_action = QtGui.QAction("&Copy",self)
        self.copy_action.setShortcut(Qt.Key_X | Qt.CTRL)
        self.copy_action.triggered.connect(self.copy)

        self.cut_action = QtGui.QAction("Cu&t",self)
        self.cut_action.setShortcut(Qt.Key_C | Qt.CTRL)
        self.cut_action.triggered.connect(self.cut)

        self.paste_action = QtGui.QAction("&Paste",self)
        self.paste_action.setShortcut(Qt.Key_V | Qt.CTRL)
        self.paste_action.triggered.connect(self.paste)

        self.undo_action = QtGui.QAction("&Undo",self)
        self.undo_action.setShortcut(Qt.Key_Z | Qt.CTRL)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QtGui.QAction("&Redo",self)
        self.redo_action.setShortcut(Qt.Key_Y | Qt.CTRL)
        self.redo_action.triggered.connect(self.redo)

        font = QtGui.QFont("Courier New",12,QtGui.QFont.Normal,False)
        self.document().setDefaultFont(font)
        
        text_option = QtGui.QTextOption()
        text_option.setAlignment(Qt.AlignLeft)
        text_option.setFlags(0)
        text_option.setTabArray([])
        text_option.setTextDirection(Qt.LeftToRight)
        text_option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(text_option)

        self.set_margin('ACTION')

        self.filename = None
        
    def set_margin(self,margin_type):
        left_margin,right_margin = self.MARGINS[margin_type]
        cursor = self.textCursor()
        block_format = cursor.blockFormat()
        block_format.setLeftMargin(left_margin)
        block_format.setRightMargin(right_margin)
        cursor.setBlockFormat(block_format)
        self.margin_type = margin_type
        
    def cycle_margin(self):
        cursor = self.textCursor()
        block_format = cursor.blockFormat()
        left_margin = block_format.leftMargin()
        if self.margin_type == 'ACTION':
            self.set_margin('NAME')
        elif self.margin_type == 'NAME':
            self.set_margin('DIALOGUE')
        else:
            self.set_margin('ACTION')

    def keyPressEvent(self,event):
        key = event.key()
        if key == Qt.Key_Tab:
            self.cycle_margin()
        elif key == Qt.Key_F5:
            self.set_margin('ACTION')
        elif key == Qt.Key_F6:
            self.set_margin('DIALOGUE')
        elif key == Qt.Key_F7:
            self.set_margin('PARENTHETICAL')
        elif key == Qt.Key_F8:
            self.set_margin('NAME')
        elif key == Qt.Key_F9:
            self.set_margin('TRANSITION')
        else:
            super().keyPressEvent(event)

    def save(self):

        if self.filename is None:
            
        
        xdownplay = ET.Element("downplay")
        xdownplay.text = "\n  "
        for tfi in self.document().rootFrame():
            text_block = tfi.currentBlock()
            if not text_block.isValid():
                xp = ET.SubElement(xdownplay,"frame")
            else:
                block_format = text_block.blockFormat()
                margin_type = self.REV_MARGINS.get(
                    block_format.leftMargin(),'ACTION')
                xp = ET.SubElement(xdownplay,"p",style=margin_type)
                xp.text = text_block.text()
            xp.tail = "\n  "
        xp.tail = "\n"
        return xdownplay

    def print_xml(self):
        xdownplay = self.to_xml()
        print(ET.tostring(xdownplay).decode())


def populate_menu(menu,menu_def):
    def def_error():
        raise ValueError("invalid menu item definition %r" % (menu_item_def,))
    for menu_item_def in menu_def:
        if isinstance(menu_item_def,QtGui.QAction):
            menu.addAction(menu_item_def)
        elif isinstance(menu_item_def,tuple):
            name,data = menu_item_def
            if not isinstance(name,str):
                def_error()
            if data is None:
                menu.addAction(name)
            elif isinstance(data,tuple):
                submenu = menu.addMenu(name)
                populate_menu(submenu,data)
            else:
                action = menu.addAction(name)
                action.triggered.connect(data)
        elif menu_item_def == "-":
            menu.addSeparator()
        else:
            def_error()
            
    
def main():
    app = QtGui.QApplication(sys.argv)
    
    script_edit = ScriptEdit()

    win = QtGui.QMainWindow()
    win.setCentralWidget(script_edit)

    menu_bar_def = [
        ( '&File', (
            ( "&New",         None ),
            ( "&Open...",     None ),
            ( "&Save",        None ),
            ( "Save &As...",  None ),
            "-",
            ( "&Export...",   None ),
            "-",
            ( "&Quit",        sys.exit ),
            ),
        ),
        ( '&Edit', (
            script_edit.undo_action,
            script_edit.redo_action,
            "-",
            script_edit.cut_action,
            script_edit.copy_action,
            script_edit.paste_action,
            ),
        ),
        ]

    menu_bar = win.menuBar()
    populate_menu(menu_bar,menu_bar_def)

    #status_bar = win.statusBar()
    #status_bar.showMessage(script_edit.margin_type)
    #script_edit.styleChanged.connect(status_bar.showMessage)
    
    win.resize(620,800) 
    win.show()
    
    app.exec_()


if __name__ == '__main__':
    main()
