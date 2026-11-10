"""A centred, live document-outline dropdown with regular-weight headings."""
from gi.repository import Gtk,Gdk,GLib,Pango

class DocumentOutline:
    def __init__(self,editor):
        self.editor=editor;self.stamp=None;self.timer=None;self.data=None;self.rows={};self.focus_on_refresh=False
        self.widget=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4,halign=Gtk.Align.CENTER,
            valign=Gtk.Align.START,margin_top=160,visible=False,width_request=360)
        self.widget.add_css_class("floating-tools");self.widget.add_css_class("outline-dropdown")
        header=Gtk.Box(spacing=8);header.add_css_class("toolbar-group")
        header.append(Gtk.Label(label="Document outline",xalign=0,hexpand=True))
        self.count=Gtk.Label(label="0 headings");self.count.add_css_class("dim-label");header.append(self.count)
        self.close=Gtk.Button(icon_name="window-close-symbolic",tooltip_text="Close outline (Esc)",focus_on_click=False)
        self.close.connect("clicked",lambda _:self.hide());header.append(self.close);self.widget.append(header)
        self.list=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,activate_on_single_click=True)
        empty=Gtk.Label(label="Apply Title or H1–H3 styles to add headings.",wrap=True,xalign=0,
            margin_top=8,margin_bottom=8,margin_start=6,margin_end=6)
        empty.add_css_class("dim-label");self.list.set_placeholder(empty)
        self.list.connect("row-activated",lambda _,row:self.choose(row.heading))
        scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            propagate_natural_height=True,max_content_height=360)
        scroll.set_child(self.list);self.widget.append(scroll)
        keys=Gtk.EventControllerKey()
        def key(_,value,code,modifiers):
            if value==Gdk.KEY_Escape:self.hide();return True
            return False
        keys.connect("key-pressed",key);self.widget.add_controller(keys)
        outside=Gtk.GestureClick(button=0,propagation_phase=Gtk.PropagationPhase.CAPTURE)
        def click(_,presses,x,y):
            if not self.widget.get_visible():return
            for target in (self.widget,editor.outline_button):
                ok,bounds=target.compute_bounds(editor)
                if ok and bounds.get_x()<=x<=bounds.get_x()+bounds.get_width() and bounds.get_y()<=y<=bounds.get_y()+bounds.get_height():return
            self.hide(False)
        outside.connect("pressed",click);editor.add_controller(outside)

    def show(self):
        if not self.editor.state.get("ready"):return
        if self.widget.get_visible():return
        self.editor.search.hide(False)
        self.widget.set_visible(True);self.editor.outline_button.set_active(True)
        self.focus_on_refresh=True;self.refresh()

    def hide(self,focus=True):
        if not self.widget.get_visible():return
        self.widget.set_visible(False);self.editor.outline_button.set_active(False)
        if self.timer:GLib.source_remove(self.timer);self.timer=None
        if focus:self.editor.focus_document()

    def refresh(self):
        self.timer=None
        if not self.widget.get_visible() or self.editor.closed:return False
        self.editor.js("window.editor.getOutline()",self.populate)
        return False

    def populate(self,data):
        if not self.widget.get_visible():return
        focus=self.editor.get_focus()
        had_focus=focus is self.list or bool(focus and focus.is_ancestor(self.list))
        self.data=data;self.stamp=(data["documentId"],data["revision"])
        if self.timer:GLib.source_remove(self.timer);self.timer=None
        row=self.list.get_row_at_index(0)
        while row:
            self.list.remove(row);row=self.list.get_row_at_index(0)
        self.rows={};has_title=any(heading["kind"]=="Title" for heading in data["headings"])
        for heading in data["headings"]:
            depth=0 if heading["kind"]=="Title" else heading["level"]-1+int(has_title)
            label=Gtk.Label(label=heading["text"],xalign=0,ellipsize=Pango.EllipsizeMode.END,
                margin_start=6+depth*16,margin_end=6,margin_top=4,margin_bottom=4)
            row=Gtk.ListBoxRow(child=label);row.heading=heading
            row.set_tooltip_text(heading["kind"]+": "+heading["text"])
            row.update_property([Gtk.AccessibleProperty.LABEL],[heading["text"]])
            self.list.append(row);self.rows[heading["position"]]=row
        count=len(data["headings"]);self.count.set_text(f"{count} heading"+('s' if count!=1 else ''))
        self.select_current(self.editor.state.get("selectionFrom",0))
        if self.focus_on_refresh or had_focus:
            self.focus_on_refresh=False
            selected=self.list.get_selected_row()
            (selected or next(iter(self.rows.values()),self.close)).grab_focus()

    def select_current(self,position):
        current=None
        for start,row in self.rows.items():
            if start<=position:current=row
        self.list.select_row(current)

    def choose(self,heading):
        data=self.data
        if not data:return
        toolbar=self.editor.glass_geometry.get("toolbar",{})
        margin=round(toolbar.get("top",64)+toolbar.get("height",90)+16)
        def jumped(success):
            if success:self.hide()
            else:self.refresh()
        self.editor.js(f'window.editor.gotoHeading({heading["position"]},{data["documentId"]},{data["revision"]},{margin})',jumped)

    def sync(self,state):
        if not self.widget.get_visible():return
        self.select_current(state.get("selectionFrom",0))
        if self.stamp!=(state["documentId"],state["revision"]) and not self.timer:
            self.timer=GLib.timeout_add(120,self.refresh)

    def dispose(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=None
