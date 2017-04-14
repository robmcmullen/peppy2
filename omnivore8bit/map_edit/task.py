""" Map editor

"""
# Enthought library imports.
from pyface.api import GUI, ImageResource, ConfirmationDialog, FileDialog, \
    ImageResource, YES, OK, CANCEL
from pyface.action.api import Action, ActionItem, Separator, Group
from pyface.tasks.api import Task, TaskWindow, TaskLayout, PaneItem, IEditor, \
    IEditorAreaPane, EditorAreaPane, Editor, DockPane, HSplitter, VSplitter
from pyface.tasks.action.api import DockPaneToggleGroup, SMenuBar, \
    SMenu, SToolBar, TaskAction, TaskToggleGroup, EditorAction, SchemaAddition
from traits.api import on_trait_change, Property, Instance, Any, Event, Int

from omnivore.framework.actions import *
from map_editor import MapEditor
from preferences import MapEditPreferences
from commands import *
from omnivore8bit.hex_edit.task import HexEditTask
from omnivore8bit.hex_edit.actions import *
import omnivore8bit.arch.fonts as fonts
import omnivore8bit.arch.colors as colors
import pane_layout
from omnivore.framework.toolbar import get_toolbar_group


class MapEditTask(HexEditTask):
    """ Tile-based map editor
    """

    new_file_text = "Map File"

    editor_id = "omnivore.map_edit"

    pane_layout_version = pane_layout.pane_layout_version

    #### Task interface #######################################################

    id = editor_id + "." + pane_layout_version if pane_layout_version else editor_id
    name = 'Map Editor'

    preferences_helper = MapEditPreferences

    #### Menu events ##########################################################

    ui_layout_overrides = {
        "menu": {
            "order": ["File", "Edit", "View", "Segment", "Documents", "Window", "Help"],
            "View": ["ViewZoomGroup", "ViewChangeGroup", "ViewConfigGroup", "ViewToggleGroup", "TaskGroup", "ViewDebugGroup"],
            "Segment": ["ListGroup"],
        },
    }

    ###########################################################################
    # 'Task' interface.
    ###########################################################################

    def _default_layout_default(self):
        return pane_layout.pane_layout()

    def create_dock_panes(self):
        return pane_layout.pane_create()

    def _tool_bars_default(self):
        toolbars = []
        toolbars.append(get_toolbar_group("%s:Modes" % self.id, MapEditor.valid_mouse_modes))
        toolbars.extend(HexEditTask._tool_bars_default(self))
        return toolbars

    ###########################################################################
    # 'FrameworkTask' interface.
    ###########################################################################

    def get_editor(self, guess=None):
        """ Opens a new empty window
        """
        editor = MapEditor()
        return editor

    @on_trait_change('window.application.preferences_changed_event')
    def refresh_from_new_preferences(self):
        e = self.active_editor
        if e is not None:
            prefs = self.preferences

    def get_actions_Menu_View_ViewConfigGroup(self):
        return self.get_common_ViewConfigGroup()

    def get_actions_Menu_View_ViewChangeGroup(self):
        font_mapping_actions = self.get_font_mapping_actions()
        font_renderer_actions = self.get_font_renderer_actions()
        return [
            SMenu(
                Group(
                    ColorStandardAction(name="NTSC", color_standard=0),
                    ColorStandardAction(name="PAL", color_standard=1),
                    id="a0", separator=True),
                Group(
                    UseColorsAction(name="Powerup Colors", colors=colors.powerup_colors()),
                    id="a1", separator=True),
                Group(
                    AnticColorAction(),
                    id="a2", separator=True),
                id='mm4', separator=False, name="Colors"),
            SMenu(
                Group(
                    UseFontAction(font=fonts.A8DefaultFont),
                    UseFontAction(font=fonts.A8ComputerFont),
                    UseFontAction(font=fonts.A2DefaultFont),
                    UseFontAction(font=fonts.A2MouseTextFont),
                    id="a1", separator=True),
                FontChoiceGroup(id="a2", separator=True),
                Group(
                    LoadFontAction(),
                    GetFontFromSelectionAction(),
                    id="a3", separator=True),
                id='mm5', separator=False, name="Font"),
            SMenu(
                Group(
                    *font_renderer_actions,
                    id="a1", separator=True),
                Group(
                    *font_mapping_actions,
                    id="a2", separator=True),
                Group(
                    FontMappingWidthAction(),
                    id="a3", separator=True),
                id='mm6', separator=False, name="Character Display"),
            ]

    ###
    @classmethod
    def can_edit(cls, document):
        return document.metadata.mime == "application/octet-stream" or document.segments

    @classmethod
    def get_match_score(cls, document):
        """Return a number based on how good of a match this task is to the
        incoming Document.
        
        0 = generic match
        ...
        10 = absolute match
        """
        return 0
