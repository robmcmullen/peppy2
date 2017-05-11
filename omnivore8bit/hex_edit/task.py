""" Text editor sample task

"""
# Enthought library imports.
from pyface.action.api import Separator, Group
from pyface.tasks.api import Task, TaskWindow, TaskLayout, PaneItem, IEditor, \
    IEditorAreaPane, EditorAreaPane, Editor, DockPane, HSplitter, VSplitter
from pyface.tasks.action.api import SMenuBar, SMenu, SToolBar, SchemaAddition
from traits.api import on_trait_change, Property, Instance, Any, Event, Int

from omnivore.framework.task import FrameworkTask
from omnivore.framework.actions import *
from hex_editor import HexEditor
from preferences import HexEditPreferences
from actions import *
import pane_layout
import omnivore8bit.arch.fonts as fonts
import omnivore8bit.arch.colors as colors
import omnivore8bit.arch.machine as machine
from omnivore8bit.utils.segmentutil import iter_known_segment_parsers
from grid_control import ByteTable
from disassembly import DisassemblyTable


class HexEditTask(FrameworkTask):
    """The hex editor was designed for reverse engineering 6502 machine code,
    initially for the Atari 8-bit computer systems, but expanded to Apple ][
    and other 6502-based processors. There is also support for most other 8-bit
    processors, but as the author doesn't have experience with other 8-bit
    processors they have not been extensively tested.

    Opening a file to edit will present the main hex edit user interface that
    shows many different views of the data. There are regions to edit hex data,
    character data, and the disassembly. There is also a bitmap view but is
    presently only for viewing, not editing.

    Editing Data
    ------------

    Hex data can be edited by:

     * clicking on a cell and changing the hex data
     * selecting a region (or multiple regions; see `Selections`_ below) and using one of the operations in the `Bytes Menu`_
     * cutting and pasting hex data from elsewhere in the file
     * cutting and pasting hex data from another file edited in a different tab or window
     * pasting in data from an external application.

    Character data can be edited by clicking on a character in the character
    map to set the cursor and then typing. Inverse text is supported for Atari
    modes. Also supported are all the selection and cut/paste methods as above.

    Baseline Data
    -------------

    Omnivore automatically highlights changes to each segment as compared to
    the state of the data when first loaded.

    Optionally, you can specify a baseline difference file to compare to a
    different set of data, like a canonical or reference image. This is useful
    to compare changes to some known state over several Omnivore editing
    sessions, as Omnivore will remember the path to the reference image and
    will reload it when the disk image is edited in the future.

    As data is changed, the changes as compared to the baseline will be
    displayed in red.

    By default, baseline data difference highlighting is turned on, you can
    change this with the `Show Baseline Differences`_ menu item.

    Selections
    ----------

    Comments
    --------

    Disassembler
    ------------

    Labels
    ~~~~~~

    Labels can be set on an address, and the label will be reflected in the
    disassembly code. Also, memory mapping files can be supplied that
    automatically label operating system locations.

    Mini-Assembler
    ~~~~~~~~~~~~~~

    The disassembly can be edited using a simple mini-assembler; clicking on an
    opcode provides a text entry box to change the command. The mini-assembler
    supports all CPU types, not just 6502.

    Data Regions
    ~~~~~~~~~~~~

    To support reverse engineering, regions can be marked as data, code, ANTIC
    display lists, and other types. Regions are highlighted in a different
    style and changes how the disassembly is displayed.

    Static Tracing of Disassembly
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    To help identify regions, static tracing can be used. Turning on static
    tracing assumes that every byte is data and shows temporary highlights over
    the entire segment. Starting a trace at an address causes Omnivore to
    follow the path of execution until it hits a return, break or bad
    instruction, marking every byte that it traverses as code. It will also
    follow both code paths at any branch. This is not an emulator, however, so
    it is not able to tell if there is any self-modifying code. Any blocks of
    code that aren't reached will require additional traces. When tracing is
    finished, the results can be applied to the segment to mark as data or
    code.


    Search
    ------

    """

    new_file_text = ["Blank Atari DOS 2 SD (90K) Image", "Blank Atari DOS 2 DD (180K) Image", "Blank Atari DOS 2 ED (130K) Image", "Blank Apple DOS 3.3 Image"]

    editor_id = "omnivore.hex_edit"

    pane_layout_version = pane_layout.pane_layout_version

    hex_grid_lower_case = Bool(True)

    assembly_lower_case = Bool(False)

    #### Task interface #######################################################

    id = editor_id + "." + pane_layout_version if pane_layout_version else editor_id
    name = 'Hex Editor'

    preferences_helper = HexEditPreferences

    #### Menu events ##########################################################

    machine_menu_changed = Event

    emulator_changed = Event

    segments_changed = Event

    # Must use different trait event in order for actions populated in the
    # dynamic menu (set by segments_changed event above) to have their radio
    # buttons updated properly
    segment_selected = Event

    ui_layout_overrides = {
        "menu": {
            "order": ["File", "Edit", "View", "Bytes", "Segment", "Disk Image", "Documents", "Window", "Help"],
            "View": ["PredefinedGroup", "ProcessorGroup", "AssemblerGroup", "MemoryMapGroup", "ColorGroup", "FontGroup", "BitmapGroup", "ZoomGroup", "ChangeGroup", "ConfigGroup", "ToggleGroup", "TaskGroup", "DebugGroup"],
            "Bytes": ["HexModifyGroup"],
            "Segment": ["ListGroup", "ActionGroup"],
            "Disk Image": ["ParserGroup", "EmulatorGroup", "ActionGroup"],
        },
    }

    ###########################################################################
    # 'Task' interface.
    ###########################################################################

    def _hex_grid_lower_case_default(self):
        prefs = self.preferences
        return prefs.hex_grid_lower_case

    def _assembly_lower_case_default(self):
        prefs = self.preferences
        return prefs.assembly_lower_case

    def _default_layout_default(self):
        return pane_layout.pane_layout()

    def create_dock_panes(self):
        return pane_layout.pane_create()

    def _active_editor_changed(self, editor):
        # Make sure it's a valid document before refreshing
        if editor is not None and editor.document.segments:
            editor.rebuild_ui()

    # Properties

    @property
    def hex_format_character(self):
        return "x" if self.hex_grid_lower_case else "X"

    ###########################################################################
    # 'FrameworkTask' interface.
    ###########################################################################

    def get_editor(self, guess=None):
        """ Opens a new empty window
        """
        editor = HexEditor()
        return editor

    @on_trait_change('window.application.preferences_changed_event')
    def refresh_from_new_preferences(self):
        prefs = self.preferences
        self.hex_grid_lower_case = prefs.hex_grid_lower_case
        self.assembly_lower_case = prefs.assembly_lower_case
        e = self.active_editor
        if e is not None:
            e.process_preference_change(prefs)
            e.reconfigure_panes()

    def get_font_mapping_actions(self, task=None):
        # When actions are needed for a popup, the task must be supplied. When
        # used from a menubar, supplying the task can mess up the EditorAction
        # automatic trait stuff, so this hack is needed. At least it is now,
        # after the addition of the Machine menu in b17fa9fe9. For some reason.
        if task is not None:
            kwargs = {'task': task}
        else:
            kwargs = {}
        actions = []
        for m in machine.predefined['font_mapping']:
            actions.append(FontMappingAction(font_mapping=m, **kwargs))
        return actions

    def get_actions_Menu_File_ImportGroup(self):
        return [
            InsertFileAction(),
            ]

    def get_actions_Menu_File_ExportGroup(self):
        return [
            SaveAsXEXAction(),
            SaveAsXEXBootAction(),
            ]

    def get_actions_Menu_File_SaveGroup(self):
        return [
            SaveAction(),
            SaveAsAction(),
            SMenu(SaveSegmentGroup(),
                  id='SaveSegmentAsSubmenu', name="Save Segment As"),
            SaveAsImageAction(),
            ]

    def get_actions_Menu_Edit_UndoGroup(self):
        return [
            UndoAction(),
            RedoAction(),
            RevertToBaselineAction(),
            ]

    def get_actions_Menu_Edit_CopyPasteGroup(self):
        return [
            CutAction(),
            CopyAction(),
            SMenu(
                CopyDisassemblyAction(),
                CopyCommentsAction(),
                CopyAsReprAction(),
                id='copyspecial', name="Copy Special"),
            PasteAction(),
            SMenu(
                PasteAndRepeatAction(),
                PasteCommentsAction(),
                id='pastespecial', name="Paste Special"),
            ]

    def get_actions_Menu_Edit_SelectGroup(self):
        return [
            SelectAllAction(),
            SelectNoneAction(),
            SelectInvertAction(),
            SMenu(
                MarkSelectionAsCodeAction(),
                MarkSelectionAsDataAction(),
                MarkSelectionAsUninitializedDataAction(),
                MarkSelectionAsDisplayListAction(),
                MarkSelectionAsJumpmanLevelAction(),
                MarkSelectionAsJumpmanHarvestAction(),
                id="mark1", name="Mark Selection As"),
            ]

    def get_actions_Menu_Edit_FindGroup(self):
        return [
            FindAction(),
            FindAlgorithmAction(),
            FindNextAction(),
            FindToSelectionAction(),
            ]

    def get_actions_Menu_View_ConfigGroup(self):
        return [
            ViewDiffHighlightAction(),
            TextFontAction(),
            ]

    def get_actions_Menu_View_PredefinedGroup(self):
        actions = []
        for m in machine.predefined['machine']:
            actions.append(PredefinedMachineAction(machine=m))
        return [
            SMenu(
                Group(
                    *actions,
                    id="a1", separator=True),
                id='MachineChoiceSubmenu1', separator=False, name="Predefined Machines"),
            ]

    def get_actions_Menu_View_ProcessorGroup(self):
        actions = []
        for r in machine.predefined['disassembler']:
            actions.append(ProcessorTypeAction(disassembler=r))
        return [
            SMenu(
                Group(
                    *actions,
                    id="a1", separator=True),
                id='mm1', separator=True, name="Processor"),
            ]

    def get_actions_Menu_View_AssemblerGroup(self):
        return [
            SMenu(
                AssemblerChoiceGroup(id="a2", separator=True),
                Group(
                    AddNewAssemblerAction(),
                    EditAssemblersAction(),
                    SetSystemDefaultAssemblerAction(),
                    id="a3", separator=True),
                id='mm2', separator=False, name="Assembler Syntax"),
            ]

    def get_actions_Menu_View_MemoryMapGroup(self):
        actions = []
        for r in machine.predefined['memory_map']:
            actions.append(MemoryMapAction(memory_map=r))
        return [
            SMenu(
                Group(
                    *actions,
                    id="a1", separator=True),
                id='mm3', separator=False, name="Memory Map"),
            ]

    def get_actions_Menu_View_ColorGroup(self):
        return [
            SMenu(
                Group(
                    ColorStandardAction(name="NTSC", color_standard=0),
                    ColorStandardAction(name="PAL", color_standard=1),
                    id="a0", separator=True),
                Group(
                    UseColorsAction(name="ANTIC Powerup Colors", colors=colors.powerup_colors()),
                    id="a1", separator=True),
                Group(
                    AnticColorAction(),
                    id="a2", separator=True),
                id='mm4', separator=False, name="Colors"),
            ]

    def get_actions_Menu_View_FontGroup(self):
        font_mapping_actions = self.get_font_mapping_actions()
        font_renderer_actions = []
        for r in machine.predefined['font_renderer']:
            font_renderer_actions.append(FontRendererAction(font_renderer=r))
        return [
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

    def get_actions_Menu_View_BitmapGroup(self):
        actions = []
        for r in machine.predefined['bitmap_renderer']:
            actions.append(BitmapRendererAction(bitmap_renderer=r))
        return [
            SMenu(
                Group(
                    *actions,
                    id="a1", separator=True),
                Group(
                    BitmapWidthAction(),
                    BitmapZoomAction(),
                    id="a1", separator=True),
                id='mm7', separator=False, name="Bitmap Display"),
            ]

    def get_actions_Menu_DiskImage_EmulatorGroup(self):
        return [
            RunEmulatorAction(),
            SMenu(
                EmulatorChoiceGroup(id="a2"),
                Group(
                    AddNewEmulatorAction(),
                    EditEmulatorsAction(),
                    SetSystemDefaultEmulatorAction(),
                    id="a3", separator=True),
                id='MachineEmulator1', name="Emulators"),
            ]

    def get_actions_Menu_DiskImage_ParserGroup(self):
        groups = []
        for mime, pretty, parsers in iter_known_segment_parsers():
            actions = [SegmentParserAction(segment_parser=s) for s in parsers]
            if not pretty:
                groups.append(Group(CurrentSegmentParserAction(), separator=True))
                groups.append(Group(*actions, separator=True))
            else:
                groups.append(SMenu(Group(*actions, separator=True), name=pretty))
        return [
            SMenu(
                *groups,
                id='submenu1', separator=False, name="File Type"),
            ]

    def get_actions_Menu_DiskImage_ActionGroup(self):
        return [
            ExpandDocumentAction(),
            Separator(),
            LoadBaselineVersionAction(),
            FindNextBaselineDiffAction(),
            FindPrevBaselineDiffAction(),
            ListDiffAction(),
            Separator(),
            SegmentGotoAction(),
            ]

    def get_actions_Menu_Segment_ListGroup(self):
        return [
            SMenu(
                SegmentChoiceGroup(id="a2", separator=True),
                id='segmentlist1', separator=False, name="View Segment"),
            ]

    def get_actions_Menu_Segment_ActionGroup(self):
        return [
            GetSegmentFromSelectionAction(),
            MultipleSegmentsFromSelectionAction(),
            InterleaveSegmentsAction(),
            SetSegmentOriginAction(),
            Separator(),
            AddCommentAction(),
            RemoveCommentAction(),
            AddLabelAction(),
            RemoveLabelAction(),
            SMenu(
                Group(
                    ImportSegmentLabelsAction(name="Import"),
                    id="sl1", separator=True),
                Group(
                    ExportSegmentLabelsAction(name="Export User Defined Labels"),
                    ExportSegmentLabelsAction(name="Export All Labels", include_disassembly_labels=True),
                    id="sl2", separator=True),
                id='segmentlabels1', separator=False, name="Manage Segment Labels"),
            Separator(),
            StartTraceAction(),
            AddTraceStartPointAction(),
            ApplyTraceSegmentAction(),
            ClearTraceAction(),
            ]

    def get_actions_Menu_Bytes_HexModifyGroup(self):
        return [
            ZeroAction(),
            FFAction(),
            NOPAction(),
            SetValueAction(),
            Separator(),
            SetHighBitAction(),
            ClearHighBitAction(),
            BitwiseNotAction(),
            OrWithAction(),
            AndWithAction(),
            XorWithAction(),
            Separator(),
            LeftShiftAction(),
            RightShiftAction(),
            LeftRotateAction(),
            RightRotateAction(),
            ReverseBitsAction(),
            Separator(),
            AddValueAction(),
            SubtractValueAction(),
            SubtractFromAction(),
            MultiplyAction(),
            DivideByAction(),
            DivideFromAction(),
            Separator(),
            RampUpAction(),
            RampDownAction(),
            ]

    def get_keyboard_actions(self):
        return [
            FindPrevAction(),
            CancelMinibufferAction(),
            UndoCursorPositionAction(),
            RedoCursorPositionAction(),
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
        return 1
