# Standard library imports.
import sys
import os

# Major package imports.
import wx
import numpy as np
import json

# Local imports.
from .tile_manager_base_editor import TileManagerBase
from ..document import DiskImageDocument

from sawx.filesystem import fsopen
from sawx.utils.processutil import run_detach

from .linked_base import LinkedBase

import logging
log = logging.getLogger(__name__)


class DummyLinkedBase(object):
    segment = None
    segment_uuid = 0

class DummyFocusedViewer(object):
    linked_base = DummyLinkedBase


class ByteEditor(TileManagerBase):
    """Edit binary files

    The views can be restored from data saved in the .omnivore file. The
    metadata file uses the editor name as a keyword into that saved data, so
    multiple editors can save data in the same metadata file without stomping
    over each other.

    The .omnivore file (a JSON file) will contain the editor name as the
    keyword, and editor-specific data below that. Editors should not touch
    anything in the metadata file outside of their keyword, but should save any
    keywords that exist in the file.

    E.g. the file may look like this:

        {
            "omnivore.byte_edit": {
                "layout": {
                    "sidebars": [ ... ],
                    "tile_manager": { .... },
                },
                "viewers": [
                    ...
                ],
                "linked_base_view_segment_uuid" {
                    "uuid1": 0,
                    "uuid2": 3,
                }.
            "omnivore.emulator": {
                ...
            }
        }
    """
    name = "omnivore.byte_edit"
    ui_name = "Byte Editor"

    default_viewers = "hex,bitmap,char,disasm"
    default_viewers = "hex,bitmap,disasm"

    preferences_module = "omnivore.editors.byte_editor_preferences"

    menubar_desc = [
        ["File",
            ["New",
                "new_blank_file",
                None,
                "new_file_from_template",
            ],
            "open_file",
            ["Open Recent",
                "open_recent",
            ],
            None,
            "save_file",
            "save_as",
            None,
            "quit",
        ],
        ["Edit",
            "undo",
            "redo",
            None,
            "copy",
            "cut",
            "paste",
            None,
            "select_all",
            "select_none",
            "select_invert",
            None,
            "prefs",
        ],
        ["View",
            "view_width",
            "view_zoom",
            ["Colors",
                "view_color_standards",
                None,
                "view_antic_powerup_colors",
                None,
                "view_ask_colors",
            ],
            ["Bitmap",
                "view_bitmap_renderers",
            ],
            ["Text",
                "view_font_renderers",
                None,
                "view_font_mappings",
            ],
            ["Font",
                "view_fonts",
                None,
                "view_font_groups",
                None,
                "view_load_font",
                "view_font_from_selection",
                "view_font_from_segment",
            ],
            None,
            ["Add Data Viewer",
                "view_add_viewer",
            ],
            ["Add Emulation Viewer",
                "view_add_emulation_viewer",
            ],
        ],
        ["Bytes",
            "byte_set_to_zero",
            "byte_set_to_ff",
            "byte_nop",
            None,
            "byte_set_high_bit",
            "byte_clear_high_bit",
            "byte_bitwise_not",
            "byte_shift_left",
            "byte_shift_right",
            "byte_rotate_left",
            "byte_rotate_right",
            "byte_reverse_bits",
            "byte_random",
            None,
            "byte_set_value",
            "byte_or_with_value",
            "byte_and_with_value",
            "byte_xor_with_value",
            None,
            "byte_ramp_up",
            "byte_ramp_down",
            "byte_add_value",
            "byte_subtract_value",
            "byte_subtract_from",
            "byte_multiply_by",
            "byte_divide_by",
            "byte_divide_from",
            None,
            "byte_reverse_selection",
            "byte_reverse_group",],
        ["Jumpman",
            ["Edit Level",
                "jumpman_level_list",
            ],
            None,
            "clear_trigger",
            "set_trigger",
            None,
            "add_assembly_source",
            "recompile_assembly_source",
        ],
        ["Media",
            "generate_segment_menu()",
            None,
            "segment_from_selection",
            "segment_multiple_from_selection",
            "segment_interleave",
            "segment_origin",
            None,
            "segment_goto",
            None,
            ["Mark Selection As",
                "disasm_type",
            ],
        ],
        ["Machine",
            ["CPU",
                "doc_cpu",
            ],
            ["Operating System",
                "doc_os_labels",
            ],
            ["Assembler Syntax",
                "doc_assembler"],
        ],
        ["Help",
            "about",
        ],
    ]

    keybinding_desc = {
        "byte_set_to_zero": "Ctrl+0",
        "byte_set_to_ff": "Ctrl+9",
        "byte_nop": "Ctrl+3",
        "byte_set_high_bit": "",
        "byte_clear_high_bit": "",
        "byte_bitwise_not": "Ctrl+1",
        "byte_shift_left": "",
        "byte_shift_right": "",
        "byte_rotate_left": "Ctrl+<",
        "byte_rotate_right": "Ctrl+>",
        "byte_reverse_bits": "",
        "byte_random": "",
        "byte_set_value": "",
        "byte_or_with_value": "Ctrl+\\",
        "byte_and_with_value": "Ctrl+7",
        "byte_xor_with_value": "Ctrl+6",
        "byte_ramp_up": "",
        "byte_ramp_down": "",
        "byte_add_value": "Ctrl+=",
        "byte_subtract_value": "Ctrl+-",
        "byte_subtract_from": "Shift+Ctrl+-",
        "byte_multiply_by": "Ctrl+8",
        "byte_divide_by": "Ctrl+/",
        "byte_divide_from": "Shift+Ctrl+/",
        "byte_reverse_selection": "",
        "byte_reverse_group": "",
    }

    module_search_order = ["omnivore.viewers.actions", "omnivore.editors.actions", "sawx.actions", "omnivore.jumpman.actions"]

    # Convenience functions

    @property
    def segment(self):
        return self.focused_viewer.linked_base.segment

    @property
    def segments(self):
        return self.document.segments

    @property
    def linked_base(self):
        return self.focused_viewer.linked_base

    @property
    def segment_uuid(self):
        return self.focused_viewer.linked_base.segment_uuid

    @property
    def section_name(self):
        return str(self.segment)

    @property
    def can_copy(self):
        return self.focused_viewer.can_copy

    #### Initialization

    def __init__(self, document, action_factory_lookup=None):
        TileManagerBase.__init__(self, document, action_factory_lookup)
        self.center_base = None
        self.linked_bases = {}

    @classmethod
    def can_edit_document_exact(cls, document):
        return "atrip_collection" in document.file_metadata

    @classmethod
    def can_edit_document_generic(cls, document):
        return document.mime == "application/octet-stream"

    #### ui

    def generate_segment_menu(self):
        items = []
        for index, container in enumerate(self.document.collection.containers):
            sub_items = [str(container), f"segment_select{{{index}}}"]
            items.append(sub_items)
        return items

    #### file handling

    def show(self, args=None):
        print("document", self.document)
        print("collection", self.document.collection)
        print("segments", self.document.segments)
        if self.has_command_line_viewer_override(args):
            self.create_layout_from_args(args)
        else:
            s = self.document.last_session.get(self.name, {})
            self.restore_session(s)
        self.set_initial_focused_viewer()
        self.document.recalc_event()

    def create_layout_from_args(self, args):
        log.debug(f"Creating layout from {args}")
        self.center_base = LinkedBase(self)
        self.linked_bases = {self.center_base.uuid:self.center_base}
        viewer_metadata = {}
        for name, value in args.items():
            viewer_metadata[name.strip()] = {}
        self.create_viewers(viewer_metadata)
        self.center_base.view_segment_uuid(None)

    def restore_session(self, s):
        log.debug("metadata: %s" % str(s))
        if 'diff highlight' in s:
            self.diff_highlight = bool(s['diff highlight'])
        self.restore_linked_bases(s)
        self.restore_layout_and_viewers(s)
        self.restore_view_segment_uuid(s)

    def restore_linked_bases(self, s):
        linked_bases = {}
        for b in s.get("linked bases", []):
            base = LinkedBase(editor=self)
            base.restore_session(b)
            linked_bases[base.uuid] = base
            log.debug("metadata: linked_base[%s]=%s" % (base.uuid, base))
        uuid = s.get("center_base", None)
        try:
            self.center_base = linked_bases[uuid]
        except KeyError:
            self.center_base = LinkedBase(editor=self)
            linked_bases[self.center_base.uuid] = self.center_base

        log.critical(f"linked_bases: {linked_bases}")
        self.linked_bases = linked_bases

    def restore_view_segment_uuid(self, s):
        for uuid, lb in self.linked_bases.items():
            segment_uuid = lb.restore_session_segment_uuid
            log.debug(f"restore_view_segment_uuid: {uuid}->{segment_uuid}")
            lb.view_segment_uuid(segment_uuid)

    def rebuild_document_properties(self):
        if not self.document.has_baseline:
            self.use_self_as_baseline(self.document)
        FrameworkEditor.rebuild_document_properties(self)
        b = self.focused_viewer.linked_base
        if b.segment_uuid is None:
            self.document.find_initial_visible_segment(b)
        log.debug("rebuilding document %s; initial segment=%s" % (str(self.document), b.segment))
        self.compare_to_baseline()
        self.can_resize_document = self.document.can_resize

    def init_view_properties(self):
        wx.CallAfter(self.force_focus, self.focused_viewer)
        self.task.machine_menu_changed = self.focused_viewer.machine
        # if self.initial_font_segment:
        #     self.focused_viewer.linked_base.machine.change_font_data(self.initial_font_segment)

    def process_preference_change(self, prefs):
        log.debug("%s processing preferences change" % self.task.name)
        #self.machine.set_text_font(prefs.text_font)

    ##### Copy/paste

    @property
    def clipboard_data_format(self):
        return self.focused_viewer.clipboard_data_format

    def calc_clipboard_data_from(self, focused):
        print("FOCUSED CONTROL", focused)
        # FIXME: for the moment, assume focused control is in focused viewer
        data_objs = self.focused_viewer.control.calc_clipboard_data_objs(focused)
        return data_objs

    def get_paste_data_from_clipboard(self):
        return clipboard.get_paste_data(self.focused_viewer)

    def process_paste_data(self, serialized_data, cmd_cls=None, *args, **kwargs):
        if cmd_cls is None:
            cmd = self.focused_viewer.get_paste_command(serialized_data, *args, **kwargs)
        else:
            cmd = cmd_cls(self.segment, serialized_data, *args, **kwargs)
        log.debug("processing paste object %s" % cmd)
        self.process_command(cmd)
        return cmd

    @property
    def supported_clipboard_data_objects(self):
        return self.focused_viewer.supported_clipboard_data_objects

    def select_all(self):
        self.focused_viewer.select_all()
        self.linked_base.refresh_event(flags=True)

    def select_none(self):
        self.focused_viewer.select_none()
        self.linked_base.refresh_event(flags=True)

    def select_invert(self):
        self.focused_viewer.select_invert()
        self.linked_base.refresh_event(flags=True)

    def check_document_change(self):
        self.document.change_count += 1
        self.update_caret_history()

    def refresh_panes(self):
        log.debug("refresh_panes called")

    def reconfigure_panes(self):
        self.update_pane_names()

    def update_pane_names(self):
        for viewer in self.viewers:
            viewer.update_caption()
        self.control.update_captions()

    def view_segment_uuid(self, uuid):
        base = self.focused_viewer.linked_base
        base.view_segment_uuid(uuid)
        self.update_pane_names()

    def get_extra_segment_savers(self, segment):
        savers = []
        for v in self.viewers:
            savers.extend(v.get_extra_segment_savers(segment))
        return savers

    def save_segment(self, saver, uri):
        try:
            byte_values = saver.encode_data(self.segment, self)
            saver = lambda a,b: byte_values
            self.document.save_to_uri(uri, self, saver, save_metadata=False)
        except Exception as e:
            log.error("%s: %s" % (uri, str(e)))
            #self.window.error("Error trying to save:\n\n%s\n\n%s" % (uri, str(e)), "File Save Error")
            raise

    def show_trace(self):
        """Highlight the current trace after switching to a new segment

        """
        if self.can_trace:
            self.disassembly.update_trace_in_segment()
            self.document.change_count += 1

    ##### Search

    def invalidate_search(self):
        self.task.change_minibuffer_editor(self)

    @property
    def searchers(self):
        search_order = []
        found = set()
        for v in self.viewers:
            for s in v.searchers:
                # searchers may depend on the viewer (like the disassembly)
                # or they may be generic to the segment
                if s.ui_name not in found:
                    search_order.append(s)
                    found.add(s.ui_name)
        log.debug("search order: %s" % [s.ui_name for s in search_order])
        return search_order

    def compare_to_baseline(self):
        if self.diff_highlight and self.document.has_baseline:
            self.document.update_baseline()

    def do_popup(self, control, popup):
        # The popup event may happen on a control that isn't the focused
        # viewer, and the focused_viewer needs to point to that control for
        # actions to work in the correct viewer. The focus needs to be forced
        # to that control, we can't necessarily count on the ActivatePane call
        # to work before the popup.
        self.focused_viewer = control.segment_viewer
        ret = FrameworkEditor.do_popup(self, control, popup)
        wx.CallAfter(self.force_focus, control.segment_viewer)
        return ret

    def process_flags(self, flags):
        """Perform the UI updates given the StatusFlags or BatchFlags flags
        
        """
        log.debug("processing flags: %s" % str(flags))
        d = self.document
        visible_range = False

        #self.caret_handler.process_caret_flags(flags, d)

        if flags.message:
            self.frame.status_message(flags.message)

        if flags.metadata_dirty:
            self.metadata_dirty = True

        control = flags.advance_caret_position_in_control
        if control:
            control.post_process_caret_flags(flags)

        if flags.data_model_changed:
            log.debug(f"process_flags: data_model_changed")
            d.data_model_changed_event(flags=flags)
            d.change_count += 1
            flags.rebuild_ui = True
        elif flags.byte_values_changed:
            log.debug(f"process_flags: byte_values_changed")
            d.change_count += 1
            d.byte_values_changed_event(flags=flags)
            flags.refresh_needed = True
        elif flags.byte_style_changed:
            log.debug(f"process_flags: byte_style_changed")
            d.change_count += 1
            d.byte_style_changed_event(flags=flags)
            flags.rebuild_ui = True
            flags.refresh_needed = True

        if flags.rebuild_ui:
            log.debug(f"process_flags: rebuild_ui")
            d.recalc_event(flags=flags)
        if flags.refresh_needed:
            log.debug(f"process_flags: refresh_needed")
            d.recalc_event(flags=flags)
