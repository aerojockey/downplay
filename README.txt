downplay.py is a very simple screenplay format editor writen in Python.

Features
--------

 * Easy, simplistic editing screenplay format.
 * Use tab or function keys to quickly choose styles.
 * Some Notepad-class editing features like search and replace.
 * A feature to estimate the all-important page count.
 * Can export scripts to PDF or plain text.
   PDF export requires reportlab.

Limitations
-----------

 * Not WYSIWIG, when printing/formatting as PDF, the line widths might
   not match what's in the editor
 * Editor does not do a great job predicting next style when hitting
   enter.
 * No bold, italic, or underline formatting.
 * No simultaneous speech or other more complex formatting.
 * No centered style.
 * Does not generate title page.

Usage
-----

It's literally one python file. You could just grab the file
downplay.py, install PySide2 and reportlab, and just run the script.

You could also get the distribution and run setup.py. (I think it can
run pip to install dependecies nowadays?)

Running downplay.py opens an app that is pretty self-explanatory.

Future
------

Since PySide2 I don't believe supports more recent versions of Python,
will have to upgrade to PySide6.
