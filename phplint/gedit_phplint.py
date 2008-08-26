# Copyright (c)  2008 - Marcus Lunzenauer <mlunzena@uos.de>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import gtk
import pango

import subprocess
import os.path
import tempfile
import time
import re

class PHPlintResultsModel (gtk.ListStore):

    def __init__ (self):
        super(PHPlintResultsModel, self).__init__ (str, int, str)

    def add (self, msg):
        self.append ([msg.stock_id, msg.lineno, msg.message])

class PHPlintResultsView (gtk.TreeView):

    def __init__ (self, panel):
        super (PHPlintResultsView, self).__init__ ()

        self._panel = panel

        icon = gtk.TreeViewColumn ("Type")
        icon_cell = gtk.CellRendererPixbuf ()
        icon.pack_start (icon_cell)
        icon.add_attribute (icon_cell, 'stock-id', 0)
        icon.set_sort_column_id (0)
        self.append_column (icon)

        linha = gtk.TreeViewColumn ("Line")
        linha_cell = gtk.CellRendererText ()
        linha.pack_start (linha_cell)
        linha.add_attribute (linha_cell, 'text', 1)
        linha.set_sort_column_id (1)
        self.append_column (linha)

        msg = gtk.TreeViewColumn ("Message")
        msg_cell = gtk.CellRendererText ()
        msg.pack_start (linha_cell)
        msg.add_attribute (linha_cell, 'text', 2)
        msg.set_sort_column_id (2)
        self.append_column (msg)

        self.connect ("row-activated", self._row_activated_cb)

    def _row_activated_cb (self, view, row, column):

        model = view.get_model ()
        iter = model.get_iter (row)

        window = self._panel.get_window ()

        doc = window.get_active_document ()
        line = model.get_value (iter, 1) - 1
        doc.goto_line (line)

        view = window.get_active_view ()

        text_iter = doc.get_iter_at_line (line)
        view.scroll_to_iter (text_iter, 0.25)



class PHPlintResultsPanel (gtk.ScrolledWindow):

    def __init__ (self, window):

        super(PHPlintResultsPanel, self).__init__ ()

        self._window = window
        self._view = PHPlintResultsView (self)

        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC);
        self.add (self._view)
        self._view.show ()

    def set_model (self, model):
        self._view.set_model (model)

    def get_window (self):
        return self._window

class PHPlintMessage (object):

    def __init__ (self, doc, msg_type, category, lineno, message, method, tag):

        self._doc = doc

        self._msg_type = msg_type
        self._category = category

        self._lineno = lineno
        self._message = message

        self._method = method
        self._tag    = tag

        self._start_iter = None
        self._end_iter   = None

        self._stock_id = self._get_stock_id (category)

    def _get_stock_id (self, category):

        if category == "error":
            return gtk.STOCK_DIALOG_ERROR

        elif category == "warning":
            return gtk.STOCK_DIALOG_WARNING

        elif category in ["convention", "refactor"]:
            return gtk.STOCK_DIALOG_INFO

        else:
            return gtk.STOCK_DIALOG_INFO

    def setWordBounds (self, start, end):
        self._start_iter = start
        self._end_iter = end

    doc     = property (lambda self: self.__doc)

    msg_type= property (lambda self: self._msg_type)
    category= property (lambda self: self._category)

    lineno  = property (lambda self: self._lineno)
    message = property (lambda self: self._message)

    method  = property (lambda self: self._method)
    tag    = property (lambda self: self._tag)

    start  = property (lambda self: self._start_iter)
    end    = property (lambda self: self._end_iter)

    stock_id = property (lambda self: self._stock_id)

class PHPlintInstance (object):

    def __init__ (self, plugin, window):
        self._plugin = plugin
        self._window = window

        self._merge_id = None
        self._action_group = None

        self._panel = None

        self._results = {}
        self._errors  = {}

        self._word_error_tags = {}
        self._line_error_tags = {}

        self._status_id = 98

        self._insert_panel ()
        self._insert_menu ()

        self._attach_events ()

    def deactivate (self):

        self._remove_menu ()
        self._remove_panel ()

        # "destroy objects"
        self._merge_id = None
        self._action_group = None

        self._panel = None
        self._results = {}

        self._merge_id = None
        self._action_group = None

        self._panel = None

        self._results = {}
        self._errors  = {}

        for doc in self._window.get_documents():
            self._remove_tags (doc)

        self._word_error_tags = {}
        self._line_error_tags = {}

        self._window = None
        self._plugin = None

    def update_ui (self):

        doc = self._window.get_active_document()

        self._action_group.set_sensitive(doc != None)

        if doc in self._results:
            self._panel.set_model (self._results[doc])

    def _insert_panel (self):

        self._panel = PHPlintResultsPanel (self._window)

        image = gtk.Image()
        image.set_from_icon_name('gnome-mime-text-x-php',
                                 gtk.ICON_SIZE_MENU)

        bottom_panel = self._window.get_bottom_panel()
        bottom_panel.add_item(self._panel, 'PHP lint Results', image)

    def _remove_panel (self):

        bottom_panel = self._window.get_bottom_panel()
        bottom_panel.remove_item(self._panel)

    def _insert_menu (self):
        manager = self._window.get_ui_manager()

        self._action_group = gtk.ActionGroup("GeditPHPlintPluginActions")
        self._action_group.set_translation_domain('phplint')
        self._action_group.add_actions([('PHPlint', None,
                                         _('PHP lint'),
                                         'F5',
                                         _('Run PHP lint for the current document'),
                                         self.on_action_PHPlint_activate)])

        manager.insert_action_group(self._action_group, -1)

        ui_str = """<ui>
                    <menubar name="MenuBar">
                     <menu name="ToolsMenu" action="Tools">
                      <placeholder name="ToolsOps_2">
                        <menuitem name="PHPlint" action="PHPlint"/>
                       </placeholder>
                      </menu>
                     </menubar>
                    </ui>"""

        self._merge_id = manager.add_ui_from_string(ui_str)

    def _remove_menu (self):
        manager = self._window.get_ui_manager ()
        manager.remove_ui (self._merge_id)
        manager.remove_action_group (self._action_group)
        manager.ensure_update ()

    def _add_tags (self, doc):

        self._word_error_tags[doc] = doc.create_tag ("PHPlint-word-error",
                                                     underline = pango.UNDERLINE_ERROR)

        self._line_error_tags[doc] = doc.create_tag ("PHPlint-line-error",
                                                     background =  "#ffc0c0")


    def _remove_tags (self, doc):

        if self._word_error_tags.has_key (doc):
            start, end = doc.get_bounds ()
            doc.remove_tag (self._word_error_tags[doc], start, end)
            doc.remove_tag (self._line_error_tags[doc], start, end)

    def _attach_events (self):
        self._window.connect ("tab_added", self.on_tab_added)
        self._window.connect ("tab_removed", self.on_tab_removed)

    def on_tab_added (self, window, tab):

        doc = tab.get_document ()

        self._results[doc] = PHPlintResultsModel ()
        self._errors[doc] = []

        # add tags to document
        self._add_tags (doc)

    def on_tab_removed (self, window, tab):

        doc = tab.get_document()
        if self._results.has_key(doc):
            self._results[doc] = None
            del self._results[doc]

            self._errors[doc] = None
            del self._errors[doc]

            self._remove_tags (doc)

    def on_action_PHPlint_activate(self, action):

        bottom_panel = self._window.get_bottom_panel()
        bottom_panel.activate_item(self._panel)

        doc = self._window.get_active_document ()

        # only run on PHP documents (not perfect, maybe use mime type too)
        if not doc.get_language () or doc.get_language().get_id () != "php":

            # flash_message is only avaiable on gedit >= 2.17.5
            status = self._window.get_statusbar ()
            try:
                status.flash_message (self._status_id, "%s is not a PHP file." % doc.get_uri_for_display ())
            except AttributeError:
                print "%s is not a PHP file." % doc.get_uri_for_display ()

            return

        # get iters and text
        start, end = doc.get_bounds ()

        text = doc.get_text (start, end)

        # save to a temporary
        in_tmpFile = tempfile.NamedTemporaryFile ("w+", suffix="-gedit-phplint")
        in_tmpFile.write (text)
        in_tmpFile.flush ()

        # build cmdline
        cmdline = "php -l %s" % in_tmpFile.name

        # run and capture output
        out_tmpFile = tempfile.NamedTemporaryFile ("w+", suffix=".gedit-phplint")

        process = subprocess.Popen (cmdline.split(" "),
                                    stdout=out_tmpFile,
                                    stderr=open('/dev/null', "w"),
                                    cwd=tempfile.gettempdir())

        process.wait ()

        # cleanup previous run errors
        self._remove_tags (doc)
        self._results[doc].clear ()

        # display results
        errors, err_lines = self._check_return (out_tmpFile)

        if errors:
            self._errors[doc] = self._parse_errors (err_lines)
            self._hightlight_errors (self._errors[doc])
            self._add_to_results (self._errors[doc])

        else:
            # no errors, just display a sucess message

            # flash message is only avaiable will be on gedit CVS as soon as my patch got accepted
            status = self._window.get_statusbar ()

            try:
                status.flash_message (self._status_id, "No errors found on %s." % doc.get_uri_for_display ())
            except AttributeError:
                print "No errors found on %s." % doc.get_uri_for_display ()


        # remove temp files
        in_tmpFile.close()
        out_tmpFile.close()

    def _check_return (self, out):
        out.flush ()
        out.seek (0)

        contents = out.readlines()

        if len(contents) >= 1:
            return True, contents[1:]
        else:
            return False, None

    def _parse_errors (self, err_lines):

        errors = []

        msg_re = re.compile(r'^(?P<type>.*):(?P<msg>.*) in (?P<file>.+) on line (?P<line>\d+)$')

        #msg_categories = dict(W='warning', E='error', C='convention', R='refactor')

        for line in err_lines:
            match = msg_re.search(line)
            if match:
                msg_type = match.group('type')
                category = "error"
                #category = msg_categories.get(msg_type[0])

                if len(msg_type) == 1:
                    msg_type = None

                filename = os.path.realpath(match.group('file'))
                lineno = int(match.group('line'))
                method = ''
                msg = match.group('msg') or ''
                #tag = self._parse_tag (msg_type, msg)
                tag = ''

                errors.append(PHPlintMessage(self._window.get_active_document,
                                            msg_type,
                                            category,
                                            int(lineno),
                                            msg,
                                            method,
                                            tag or ''))

        return errors

    def _hightlight_errors (self, errors):

        doc = self._window.get_active_document ()

        for err in errors:

            if err.category != "error":
                continue

            start = doc.get_iter_at_line (err.lineno - 1)

            end = doc.get_iter_at_line (err.lineno - 1)
            end.forward_to_line_end ()

            # apply tag to word, if any
            if err.tag:
                match_start, match_end = start.forward_search (err.tag,
                                                               gtk.TEXT_SEARCH_TEXT_ONLY,
                                                               end)
                doc.apply_tag (self._word_error_tags[doc], match_start, match_end)

            # apply tag to entire line
            doc.apply_tag (self._line_error_tags[doc], start, end)


    def _add_to_results (self, errors):

        doc = self._window.get_active_document ()

        for err in errors:
            self._results[doc].add (err)

    def _parse_tag (self, msg_type, msg):

        tag = ''

        if msg_type == "E0602":
            tag = msg[msg.find("'")+1: msg.rfind("'")]

        return tag

