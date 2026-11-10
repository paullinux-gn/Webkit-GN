"""Native floating find/replace controls; document searches run in ProseMirror."""
import json
from gi.repository import Gtk,Gdk,GLib

class SearchPill:
    def __init__(self,editor):
        self.editor=editor;self.document_id=None
        self.widget=Gtk.Box(spacing=4,halign=Gtk.Align.CENTER,valign=Gtk.Align.START,margin_top=160,visible=False)
        self.widget.add_css_class("floating-tools");self.widget.add_css_class("search-pill")
        group=Gtk.Box(spacing=4);group.add_css_class("toolbar-group");self.widget.append(group)
        self.query=Gtk.SearchEntry(placeholder_text="Find",width_chars=18,tooltip_text="Find text (Enter: next; Shift+Enter: previous)")
        self.query.update_property([Gtk.AccessibleProperty.LABEL],["Find text"])
        self.replacement=Gtk.Entry(placeholder_text="Replace with",width_chars=16)
        self.replacement.update_property([Gtk.AccessibleProperty.LABEL],["Replacement text"])
        self.counter=Gtk.Label(label="0/0");self.counter.add_css_class("match-count")
        self.case=Gtk.ToggleButton(label="Aa",tooltip_text="Match case",focus_on_click=False)
        self.case.update_property([Gtk.AccessibleProperty.LABEL],["Match case"])
        self.previous=Gtk.Button(icon_name="go-up-symbolic",tooltip_text="Previous match",focus_on_click=False)
        self.next=Gtk.Button(icon_name="go-down-symbolic",tooltip_text="Next match",focus_on_click=False)
        self.replace=Gtk.Button(label="Replace",tooltip_text="Replace current match",focus_on_click=False)
        self.replace_all=Gtk.Button(label="All",tooltip_text="Replace all matches",focus_on_click=False)
        self.close=Gtk.Button(icon_name="window-close-symbolic",tooltip_text="Close search (Esc)",focus_on_click=False)
        for item in (self.query,self.counter,self.previous,self.next,self.case,self.replacement,self.replace,self.replace_all,self.close):group.append(item)
        self.query.connect("search-changed",lambda _:self.refresh())
        self.query.connect("activate",lambda _:self.navigate(1))
        self.replacement.connect("activate",lambda _:self.replace_matches(False))
        self.case.connect("toggled",lambda _:self.refresh())
        self.previous.connect("clicked",lambda _:self.navigate(-1));self.next.connect("clicked",lambda _:self.navigate(1))
        self.replace.connect("clicked",lambda _:self.replace_matches(False));self.replace_all.connect("clicked",lambda _:self.replace_matches(True))
        self.close.connect("clicked",lambda _:self.hide())
        keys=Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        def key(_,value,code,modifiers):
            if value==Gdk.KEY_Escape:self.hide();return True
            if value in (Gdk.KEY_Return,Gdk.KEY_KP_Enter) and modifiers&Gdk.ModifierType.SHIFT_MASK:
                self.navigate(-1);return True
            return False
        keys.connect("key-pressed",key);self.widget.add_controller(keys);self.update({"count":0,"current":0})

    def show(self):
        if not self.editor.state.get("ready"):return
        if getattr(self.editor,"outline",None):self.editor.outline.hide(False)
        if not self.widget.get_visible():
            self.widget.set_visible(True);self.editor.find_button.set_active(True);self.refresh()
        self.query.grab_focus();self.query.select_region(0,-1)

    def hide(self,focus=True):
        if not self.widget.get_visible():return
        self.widget.set_visible(False);self.editor.find_button.set_active(False)
        self.editor.js("window.editor.clearSearch()",lambda _:self.editor.focus_document() if focus else None)

    def refresh(self):
        if not self.widget.get_visible():return False
        self.editor.js("window.editor.find("+json.dumps(self.query.get_text())+","+json.dumps(self.case.get_active())+")",self.update)
        return False

    def navigate(self,direction):
        self.editor.js(f"window.editor.findNext({direction})",self.update)

    def replace_matches(self,all_matches):
        self.editor.js("window.editor.replaceMatch("+json.dumps(self.replacement.get_text())+","+json.dumps(all_matches)+")",self.update)

    def update(self,result):
        count=result.get("count",0);self.counter.set_text(f'{result.get("current",0)}/{count}')
        self.counter.set_tooltip_text(f"{count} matches")
        for button in (self.previous,self.next,self.replace,self.replace_all):button.set_sensitive(count>0)
        if "replaced" in result:self.editor.status.set_label(f'{result["replaced"]} replacements')

    def sync(self,state):
        self.update(state.get("search",{"count":0,"current":0}))
        changed=self.document_id is not None and self.document_id!=state["documentId"]
        self.document_id=state["documentId"]
        if changed and self.widget.get_visible():GLib.idle_add(self.refresh)
