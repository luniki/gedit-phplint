import gedit

from gedit_phplint import PHPlintInstance

class PHPlintPlugin (gedit.Plugin):

    def __init__(self):
        self._instances = {}

        super(PHPlintPlugin, self).__init__ ()

    def activate(self, window):
        # print "Plugin activate for", window
        self._instances[window] = PHPlintInstance (self, window)

    def deactivate(self, window):
        # print "Plugin deactivate for", window

        if self._instances.has_key(window):
            self._instances[window].deactivate()
            del self._instances[window]

    def update_ui(self, window):
        # print "Plugin update_ui for", window
        if self._instances.has_key(window):
            self._instances[window].update_ui()
