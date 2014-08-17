# Standard library imports.
import sys
from os.path import basename

# Major package imports.
import wx
import wx.stc

# Enthought library imports.
from traits.api import Bool, Event, Instance, File, Unicode, Property, provides
from pyface.key_pressed_event import KeyPressedEvent

# Local imports.
from peppy2.framework.editor import FrameworkEditor
from i_hex_editor import IHexEditor
from grid_control import HexEditControl
from peppy2.utils.wx.stcbase import PeppySTC

@provides(IHexEditor)
class HexEditor(FrameworkEditor):
    """ The toolkit specific implementation of a HexEditor.  See the
    IHexEditor interface for the API documentation.
    """

    #### 'IPythonEditor' interface ############################################

    obj = Instance(File)

    #### Events ####

    changed = Event

    key_pressed = Event(KeyPressedEvent)

    ###########################################################################
    # 'PythonEditor' interface.
    ###########################################################################

    def create(self, parent):
        self.control = self._create_control(parent)

    def load(self, guess=None):
        """ Loads the contents of the editor.
        """
        if guess is None:
            path = self.path
            text = ''
        else:
            metadata = guess.get_metadata()
            path = metadata.uri
            text = guess.get_utf8()

#        self.control.SetTextUTF8(text)
        self.bytestore.SetText('')
        styledtxt = '\0'.join(text)+'\0'
        self.bytestore.AddStyledText(styledtxt)
        self.bytestore.EmptyUndoBuffer()
        self.control.Update(self.bytestore)
        self.path = path
        self.dirty = False
        
        self.disassembly.update(text)

    def save(self, path=None):
        """ Saves the contents of the editor.
        """
        if path is None:
            path = self.path

        f = file(path, 'w')
        f.write(self.control.GetTextUTF8())
        f.close()

        self.dirty = False
    
    def undo(self):
        self.bytestore.Undo()
    
    def redo(self):
        self.bytestore.Redo()

    ###########################################################################
    # Trait handlers.
    ###########################################################################


    ###########################################################################
    # Private interface.
    ###########################################################################

    def _create_control(self, parent):
        """ Creates the toolkit-specific control for the widget. """

        # Base-class constructor.
        self.bytestore = stc = PeppySTC(parent)
        self.control = HexEditControl(parent, self, stc)

        ##########################################
        # Events.
        ##########################################

        # By default, the will fire EVT_STC_CHANGE evented for all mask values
        # (STC_MODEVENTMASKALL). This generates too many events.
        stc.SetModEventMask(wx.stc.STC_MOD_INSERTTEXT |
                            wx.stc.STC_MOD_DELETETEXT |
                            wx.stc.STC_PERFORMED_UNDO |
                            wx.stc.STC_PERFORMED_REDO)

        # Listen for changes to the file.
        wx.stc.EVT_STC_CHANGE(stc, stc.GetId(), self._on_stc_changed)

        # Listen for key press events.
        wx.EVT_CHAR(stc, self._on_char)

        # Get related controls
        self.disassembly = self.window.get_dock_pane('hex_edit.mos6502_disasmbly_pane').control

        # Load the editor's contents.
        self.load()

        return self.control

    #### wx event handlers ####################################################

    def _on_stc_changed(self, event):
        """ Called whenever a change is made to the text of the document. """

        self.dirty = self.bytestore.CanUndo()
        self.can_undo = self.bytestore.CanUndo()
        self.can_redo = self.bytestore.CanRedo()
        self.changed = True

        # Give other event handlers a chance.
        event.Skip()

        return

    def _on_char(self, event):
        """ Called whenever a change is made to the text of the document. """

        self.key_pressed = KeyPressedEvent(
            alt_down     = event.m_altDown == 1,
            control_down = event.m_controlDown == 1,
            shift_down   = event.m_shiftDown == 1,
            key_code     = event.m_keyCode,
            event        = event
        )

        # Give other event handlers a chance.
        event.Skip()

        return
