#!/usr/bin/env python3
"""Native GNOME shell around a local ProseMirror editor in WebKitGTK 6."""
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

# Initialise before GTK/WebKit load their translation catalogues.
from ui_language import use_desktop_language
use_desktop_language()

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gio, GLib, Gtk, WebKit

from print_preview import PrintPreview
from search_pill import SearchPill
from outline import DocumentOutline
from document_io import read_html, write_html, image_uri
from appearance import AppearanceStore
from ui_surfaces import surface_css,compact_dialog
from toolbar import image_size_dialog,build_text_toolbar,build_action_toolbar,sync_text_toolbar,table_dialog,HIGHLIGHT_COLOURS

ROOT = Path(__file__).resolve().parent
VERSION = json.loads((ROOT/"package.json").read_text(encoding="utf-8"))["version"]
SWATCH_CSS="\n".join(f".floating-tools button.color-swatch.swatch-{index} {{ background:{value}; }}" for index,(_,value) in enumerate(HIGHLIGHT_COLOURS))


class Editor(Adw.ApplicationWindow):
    def context_menu(self, webview, menu, *args):
        # Filter stock actions rather than translated labels.
        hidden = {WebKit.ContextMenuAction.UNICODE, WebKit.ContextMenuAction.FONT_MENU}
        for item in list(menu.get_items()):
            if item.get_stock_action() in hidden:
                menu.remove(item)
        # Avoid empty groups after removing stock submenus.
        previous_separator = True
        for item in list(menu.get_items()):
            if item.is_separator():
                if previous_separator:
                    menu.remove(item)
                previous_separator = True
            else:
                previous_separator = False
        items = menu.get_items()
        if items and items[-1].is_separator():
            menu.remove(items[-1])
        GLib.idle_add(self.style_popovers)
        return False

    def __init__(self, app):
        super().__init__(application=app, title="Webkit-GN")
        self.sandboxed=Path("/.flatpak-info").is_file()
        self.add_css_class("wp-editor")
        Gtk.IconTheme.get_for_display(self.get_display()).add_search_path(str(ROOT.parent/"data/icons"))
        self.set_icon_name("io.github.paullinux_gn.WebkitGN")
        # 794 px A4 × 125%, plus paper margins, scrollbar and window borders.
        self.set_default_size(1120, 1000)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="document-io")
        self.state = {"ready":False,"dirty":False}
        self.path = None
        self.file_busy = False
        self.closed = False
        self.discard_confirmed = False
        self.syncing = False
        self.file_chooser = None
        self.image_chooser = None
        self.appearance_store=AppearanceStore(os.environ.get("GNOME_WP_SETTINGS_FILE",
            str(Path(GLib.get_user_config_dir())/"gnome-wordprocessor/interface.json")))
        self.appearance=self.appearance_store.load()
        self.preference_timer=None
        self.interface_window=None
        self.about_window=None
        self.glass_geometry={}
        self.frame_clock=None
        self.frame_handler=None
        self.native_blur=self.detect_native_blur()
        self.connect("map",self.track_glass)
        self.connect("close-request", self.on_close)

        overlay = Gtk.Overlay()
        self.set_content(overlay)
        manager = WebKit.UserContentManager()
        manager.register_script_message_handler("editor", None)
        manager.connect("script-message-received::editor", self.on_message)
        self.webview = WebKit.WebView(user_content_manager=manager,
                                     network_session=WebKit.NetworkSession.new_ephemeral())
        self.webview.connect("decide-policy", self.navigation)
        self.webview.connect("context-menu",self.context_menu)
        self.webview.connect("load-failed", self.load_failed)
        self.webview.connect("web-process-terminated", self.web_terminated)
        overlay.set_child(self.webview)

        header = Adw.HeaderBar(valign=Gtk.Align.START)
        self.header=header
        header.add_css_class("editor-header")
        self.heading = Adw.WindowTitle(title="Untitled", subtitle=f"Prototype {VERSION.removesuffix('.0')} · 125% view")
        header.set_title_widget(self.heading)
        self.file_actions={}
        files=Gio.Menu()
        for name,label,callback,accelerator in [
                ("new","New document",self.new,"<Primary>n"),
                ("open","Open…",lambda:self.file_dialog(False),"<Primary>o"),
                ("save","Save",self.save,"<Primary>s"),
                ("save-as","Save as…",lambda:self.file_dialog(True),"<Primary><Shift>s"),
                ("page-break","Insert page break",lambda:self.command("pageBreak"),"<Primary>Return"),
                ("margins","Page margins…",self.show_margins,"<Primary><Shift>m"),
                ("print-preview","Print preview…",self.show_print_preview,"<Primary><Shift>p"),
                ("print","Print…",self.print_document,"<Primary>p")]:
            action=Gio.SimpleAction.new(name,None)
            action.connect("activate",lambda _,parameter,fn=callback:fn())
            action.set_enabled(False)
            self.add_action(action);self.file_actions[name]=action
            files.append(label,"win."+name)
            app.set_accels_for_action("win."+name,[accelerator])
        action=Gio.SimpleAction.new("interface",None)
        action.connect("activate",lambda *_:self.show_interface())
        self.add_action(action)
        menu=Gio.Menu();menu.append_section(None,files)
        search_action=Gio.SimpleAction.new("find-replace",None)
        search_action.connect("activate",lambda *_:self.search.show());search_action.set_enabled(False)
        self.add_action(search_action);self.file_actions["find-replace"]=search_action
        app.set_accels_for_action("win.find-replace",["<Primary>h","<Primary>f"])
        outline_action=Gio.SimpleAction.new("document-outline",None)
        outline_action.connect("activate",lambda *_:self.outline.show());outline_action.set_enabled(False)
        self.add_action(outline_action);self.file_actions["document-outline"]=outline_action
        app.set_accels_for_action("win.document-outline",["<Primary><Shift>o"])
        search_menu=Gio.Menu();search_menu.append("Search and replace…","win.find-replace")
        search_menu.append("Document outline","win.document-outline")
        menu.append_section(None,search_menu)
        interface=Gio.Menu();interface.append("Interface…","win.interface")
        menu.append_section(None,interface)
        about_action=Gio.SimpleAction.new("about",None)
        about_action.connect("activate",lambda *_:self.show_about())
        self.add_action(about_action)
        about=Gio.Menu();about.append("About Webkit-GN","win.about")
        menu.append_section(None,about)
        self.menu_button=Gtk.MenuButton(icon_name="open-menu-symbolic",tooltip_text="Main menu")
        self.menu_button.set_menu_model(menu)
        header.pack_end(self.menu_button)
        overlay.add_overlay(header)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                        halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=64)
        panel.add_css_class("floating-tools")
        self.toggle_buttons = {}
        self.action_buttons = {}
        self.toolbar_rows=[build_text_toolbar(self),build_action_toolbar(self)]
        for index,row in enumerate(self.toolbar_rows):
            if index:
                divider=Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                divider.add_css_class("toolbar-row-divider");panel.append(divider)
            row.set_halign(Gtk.Align.FILL if index==0 else Gtk.Align.CENTER)
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,vscrollbar_policy=Gtk.PolicyType.NEVER)
            scroll.set_propagate_natural_width(True)
            scroll.set_max_content_width(960)
            scroll.set_child(row)
            panel.append(scroll)
        overlay.add_overlay(panel)
        self.tools = panel
        self.tools.set_sensitive(False)
        self.search=SearchPill(self);overlay.add_overlay(self.search.widget)
        self.outline=DocumentOutline(self);overlay.add_overlay(self.outline.widget)
        self.status = Gtk.Label(label="Starting editor…",halign=Gtk.Align.CENTER,valign=Gtk.Align.END,margin_bottom=8)
        self.status.add_css_class("editor-status")
        overlay.add_overlay(self.status)
        self.css=Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(self.get_display(),self.css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.apply_appearance()
        self.style_popovers()
        self.webview.load_uri((ROOT/"editor.html").as_uri())

    def style_popovers(self):
        def visit(widget):
            if isinstance(widget,Gtk.Popover):widget.set_has_arrow(False)
            if isinstance(widget,Gtk.PopoverMenu):widget.add_css_class("compact-action-menu")
            child=widget.get_first_child()
            while child:
                visit(child);child=child.get_next_sibling()
        for window in Gtk.Window.get_toplevels():visit(window)
        return False

    def detect_native_blur(self):
        # Same native-blur requirements as Twinly: GTK 4.24+ on Wayland.
        if (Gtk.get_major_version(),Gtk.get_minor_version())<(4,24):return False
        if 'Wayland' not in type(self.get_display()).__name__:return False
        probe=Gtk.CssProvider();errors=[]
        probe.connect("parsing-error",lambda _,section,error:errors.append(error))
        probe.load_from_string(".blur-probe { backdrop-filter: blur(1px); }")
        return not errors

    def track_glass(self,*_):
        if not self.frame_handler:
            self.frame_clock=self.get_frame_clock()
            self.frame_handler=self.frame_clock.connect("after-paint",self.update_glass_geometry)

    def update_glass_geometry(self,*_):
        if self.closed:return
        geometry={}
        ok,toolbar_bounds=self.tools.compute_bounds(self.webview)
        if ok:
            top=round(toolbar_bounds.get_y()+toolbar_bounds.get_height()+8)
            for panel in (self.search.widget,self.outline.widget):
                if panel.get_margin_top()!=top:panel.set_margin_top(top)
        for name,widget in (("header",self.header),("toolbar",self.tools),("search",self.search.widget),("outline",self.outline.widget)):
            if name in ("search","outline") and not widget.get_visible():continue
            ok,bounds=widget.compute_bounds(self.webview)
            if ok:
                geometry[name]={"left":round(bounds.get_x(),2),"top":round(bounds.get_y(),2),
                    "width":round(bounds.get_width(),2),"height":round(bounds.get_height(),2)}
        if geometry!=self.glass_geometry:
            self.glass_geometry=geometry
            self.apply_web_appearance()

    def apply_web_appearance(self):
        if self.state.get("ready") and not self.closed:
            options={**self.appearance,"fallback":not self.native_blur,"geometry":self.glass_geometry,"viewport":{"width":self.webview.get_width(),"height":self.webview.get_height()}}
            self.js("window.editor.setAppearance("+json.dumps(options)+")")

    def apply_appearance(self):
        dark=self.appearance["theme"]=="dark"
        dark_tools=self.appearance["theme"]!="light"
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK if dark_tools else Adw.ColorScheme.FORCE_LIGHT)
        self.tools.remove_css_class("dark-toolbar")
        if dark_tools:self.tools.add_css_class("dark-toolbar")
        opacity=self.appearance["opacity"] if self.appearance["blur"] else 1.0
        fallback=self.appearance["blur"] and not self.native_blur
        header_color="37,39,45" if dark else "250,250,252"
        toolbar_color="37,39,45" if dark_tools else "250,250,252"
        header_bg="transparent" if self.appearance["blur"] else f"rgba({header_color},{opacity})"
        toolbar_bg="transparent" if fallback else f"rgba({toolbar_color},{opacity})"
        header_ink="#f2f3f5" if dark else "#202124"
        toolbar_ink="#f2f3f5" if dark_tools else "#202124"
        backdrop=f'backdrop-filter: blur({self.appearance["blur_radius"]}px);' if self.native_blur and self.appearance["blur"] else ""
        self.css.load_from_data((f"""
        window.wp-editor {{ background:rgb({header_color}); border:0; }}
        .editor-header, .editor-header:backdrop {{ background: {header_bg}; background-image:none; color:{header_ink}; border:0; box-shadow:none; }}
        .editor-header button {{ color:inherit; }}
        .floating-tools {{ background:{toolbar_bg}; background-image:none; color:{toolbar_ink}; padding:4px 8px;
          border-radius:20px; border:1px solid alpha(currentColor,.10); box-shadow:0 3px 8px alpha(black,.15); {backdrop} }}
        .floating-tools label {{ color:inherit; }}
        .search-pill {{ border-radius:18px; padding:6px 8px; }}
        .search-pill entry {{ background:alpha(currentColor,.05); color:inherit;
          border:1px solid alpha(currentColor,.12); border-radius:8px; box-shadow:none; min-height:28px; }}
        .search-pill .match-count {{ min-width:48px; }}
        .outline-dropdown {{ border-radius:18px; padding:8px; }}
        .outline-dropdown list {{ background:transparent; color:inherit; }}
        .outline-dropdown label {{ font-weight:400; }}
        .outline-dropdown row {{ border-radius:6px; padding:0 2px; margin:0; }}
        .outline-dropdown row:hover {{ background:alpha(currentColor,.07); }}
        .outline-dropdown row:selected {{ background:alpha(@accent_bg_color,.18); color:@accent_color; }}
        .floating-tools, .floating-tools label, .floating-tools .toolbar-group label, .floating-tools button, .floating-tools dropdown {{ font-weight:400; }}
        .editor-status {{ background:rgba({header_color},0.94); color:{header_ink}; padding:5px 12px; border-radius:12px; }}
        .theme-choice {{ min-width:64px; min-height:64px; padding:0; border-radius:999px; border:1px solid #888; background-image:none; }}
        .theme-choice:checked {{ outline:3px solid #3584e4; outline-offset:4px; }}
        .theme-choice.light {{ background:#fafafc; }}
        .theme-choice.dark {{ background:#25272d; }}
        .theme-choice.mixed {{ background:linear-gradient(to right,#25272d 0%,#25272d 50%,#fafafc 50%,#fafafc 100%); }}
        /* Flat controls and interaction colours adapted from Twinly's theme.py. */
        .floating-tools .toolbar-group {{ background:transparent; border:0; padding:0; }}
        .floating-tools .toolbar-group > button,
        .floating-tools .toolbar-group > dropdown > button,
        .floating-tools .toolbar-group > menubutton > button {{
          min-width:24px; min-height:24px; padding:2px 4px;
          background:transparent; background-image:none; box-shadow:none;
          color:inherit; border:1px solid transparent; border-radius:6px; }}
        .floating-tools .toolbar-group > button:hover,
        .floating-tools .toolbar-group > dropdown > button:hover,
        .floating-tools .toolbar-group > menubutton > button:hover {{ background:alpha(currentColor,.07); }}
        .floating-tools .toolbar-group > button:checked,
        .floating-tools .toolbar-group > button:active,
        .floating-tools .toolbar-group > dropdown > button:checked,
        .floating-tools .toolbar-group > menubutton > button:checked {{
          background:alpha(@accent_bg_color,.18); color:@accent_color; }}
        .floating-tools .toolbar-divider,
        .floating-tools .toolbar-row-divider {{ background:alpha(currentColor,.12); min-width:1px; min-height:1px; border:0; box-shadow:none; }}
        .floating-tools .toolbar-row-divider {{ margin:0 4px; }}
        .floating-tools button.color-swatch {{ min-width:24px; min-height:24px; padding:0; border:0; border-radius:7px; box-shadow:none; background-image:none; }}
        .floating-tools button.color-swatch.swatch-clear {{ background:linear-gradient(135deg,transparent 46%,#e01b24 46%,#e01b24 54%,transparent 54%),#f3f4f7; }}
        """+SWATCH_CSS+surface_css(dark_tools,opacity,self.native_blur,self.appearance["blur_radius"],self.appearance["blur"])).encode())
        self.apply_web_appearance()

    def change_appearance(self,**changes):
        self.appearance.update(changes)
        self.apply_appearance()
        if self.preference_timer:GLib.source_remove(self.preference_timer)
        self.preference_timer=GLib.timeout_add(250,self.save_appearance)

    def save_appearance(self):
        self.preference_timer=None
        try:self.appearance_store.save(self.appearance)
        except OSError:self.status.set_label("Could not save interface preferences.")
        return False

    def show_about(self):
        if self.about_window:
            self.about_window.present();return
        window=Adw.AboutWindow(
            transient_for=self,modal=True,
            application_name="Webkit-GN",
            application_icon="io.github.paullinux_gn.WebkitGN",
            developer_name="Paullinux",version=VERSION,
            comments="A native GNOME word processor. Write and format documents locally, save self-contained HTML, and print with a paginated PDF preview.",
            website="https://github.com/paullinux-gn/Webkit-GN",
            issue_url="https://github.com/paullinux-gn/Webkit-GN/issues",
            copyright="Copyright © 2026 Paullinux",
            license_type=Gtk.License.GPL_3_0)
        window.set_developers(["Paullinux https://github.com/paullinux-gn"])
        window.add_credit_section("Built with",["GTK4 and libadwaita","WebKitGTK and PyGObject","ProseMirror","Poppler (PDF preview)"])
        window.add_credit_section("Design and artwork",["Custom Webkit-GN application icon","GNOME Project — Adwaita symbolic icon","Twinly — toolbar styling"])
        window.add_link("User guide","https://github.com/paullinux-gn/Webkit-GN#readme")
        window.add_link("Third-party licences","https://github.com/paullinux-gn/Webkit-GN/blob/main/webkit/THIRD_PARTY.md")
        def closed(*_):
            self.about_window=None
            GLib.idle_add(self.focus_document)
            return False
        window.connect("close-request",closed)
        self.about_window=window;window.present()

    def show_interface(self):
        if self.interface_window:
            self.interface_window.present();return
        window=Adw.PreferencesWindow(transient_for=self,title="Interface",default_width=392,default_height=550,search_enabled=False)
        self.interface_window=window
        window.connect("close-request",self.close_interface)
        page=Adw.PreferencesPage()
        group=Adw.PreferencesGroup(title="Theme")
        choices=Gtk.Box(spacing=36,halign=Gtk.Align.CENTER,margin_top=18,margin_bottom=18)
        self.theme_buttons={};first=None
        for key,label in (("light","Light"),("dark","Dark"),("mixed","Dark + light")):
            column=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14,halign=Gtk.Align.CENTER)
            circle=Gtk.ToggleButton(halign=Gtk.Align.CENTER,tooltip_text=label)
            circle.add_css_class("theme-choice");circle.add_css_class(key)
            circle.update_property([Gtk.AccessibleProperty.LABEL],[label+" theme"])
            if first:circle.set_group(first)
            else:first=circle
            circle.set_active(key==self.appearance["theme"])
            circle.connect("toggled",lambda button,theme=key:self.change_appearance(theme=theme) if button.get_active() else None)
            column.append(circle);choices.append(column)
            self.theme_buttons[key]=circle
        group.add(choices);page.add(group)
        glass=Adw.PreferencesGroup(title="Translucency")
        self.blur_switch=Adw.SwitchRow(title="Blur",subtitle="Headerbar, toolbar and menus" if self.native_blur else
            "Headerbar and toolbar; native menu blur requires GNOME 51+ on Wayland",active=self.appearance["blur"])
        glass.add(self.blur_switch)
        self.opacity_slider=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,100,1)
        self.opacity_slider.set_value(self.appearance["opacity"]*100);self.opacity_slider.set_digits(0)
        self.opacity_slider.set_draw_value(True)
        self.opacity_slider.set_size_request(150,-1);self.opacity_slider.set_valign(Gtk.Align.CENTER)
        row=Adw.ActionRow(title="Opacity (%)");row.add_suffix(self.opacity_slider);glass.add(row)
        self.blur_slider=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,40,1)
        self.blur_slider.set_value(self.appearance["blur_radius"]);self.blur_slider.set_digits(0)
        self.blur_slider.set_draw_value(True)
        self.blur_slider.set_size_request(150,-1);self.blur_slider.set_valign(Gtk.Align.CENTER)
        self.blur_slider.set_sensitive(self.appearance["blur"])
        row=Adw.ActionRow(title="Blur intensity");row.add_suffix(self.blur_slider);glass.add(row)
        self.blur_switch.connect("notify::active",lambda switch,_:(self.blur_slider.set_sensitive(switch.get_active()),self.change_appearance(blur=switch.get_active())))
        self.opacity_slider.connect("value-changed",lambda scale:self.change_appearance(opacity=scale.get_value()/100))
        self.blur_slider.connect("value-changed",lambda scale:self.change_appearance(blur_radius=scale.get_value()))
        page.add(glass);window.add(page);window.present()

    def close_interface(self,*_):
        self.interface_window=None
        return False

    def js(self, expression, callback=None, on_error=None):
        if self.closed:
            return
        def done(view,result,_):
            if self.closed:
                return
            try:
                value = view.evaluate_javascript_finish(result)
                data = json.loads(value.to_string())
                if callback:
                    callback(data)
            except (GLib.Error,ValueError,TypeError) as error:
                self.status.set_label(str(error))
                self.set_busy(False)
                if on_error:
                    on_error(str(error))
        self.webview.evaluate_javascript("JSON.stringify("+expression+") ?? 'null'",-1,None,None,None,done,None)

    def command(self,name,args=None):
        if self.state.get("ready"):
            self.webview.grab_focus()
            self.js("window.editor.exec("+json.dumps(name)+","+json.dumps(args or {})+")",lambda _:self.focus_document())

    def on_message(self,manager,value):
        try:
            state=json.loads(value.to_string())
        except (ValueError,AttributeError):
            return
        if state.get("type")=="edit-image" and not self.closed:
            image_size_dialog(self,state["image"]);return
        if state.get("type")=="edit-table" and not self.closed:
            table_dialog(self,state["table"]);return
        if state.get("type")!="state" or self.closed:
            return
        previous=self.state
        first = not previous.get("ready")
        self.state=state
        self.tools.set_sensitive(True)
        self.syncing=True
        self.action_buttons["undo"].set_sensitive(state["canUndo"])
        self.action_buttons["redo"].set_sensitive(state["canRedo"])
        toolbar_changed=(first or state["format"]!=previous.get("format") or state["styles"]!=previous.get("styles")
            or any(bool(state.get(name))!=bool(previous.get(name)) for name in ("table","textbox","image")))
        if toolbar_changed:
            names={"bold":"strong","italic":"em","underline":"underline","strike":"strike",
                   "subscript":"subscript","superscript":"superscript","checklist":"checklist"}
            for command,widget in self.toggle_buttons.items():
                widget.set_active(bool(state["format"].get(names[command])))
            sync_text_toolbar(self,state)
        self.search.sync(state)
        self.outline.sync(state)
        self.syncing=False
        self.update_title()
        if not self.file_busy:
            self.status.set_label(f'{state["words"]} words · Continuous document')
        if first:
            self.set_busy(False)
            self.apply_web_appearance()
            self.focus_document()

    def update_title(self):
        self.heading.set_title((self.path.name if self.path else "Untitled")+(" •" if self.state.get("dirty") else ""))

    def focus_document(self):
        if not self.closed and self.state.get("ready"):
            self.webview.grab_focus()
            self.js("window.editor.focus()")
        return False

    def set_busy(self,busy):
        self.file_busy=busy
        for action in self.file_actions.values():
            action.set_enabled(not busy)

    def work(self,fn,callback):
        future=self.executor.submit(fn)
        def complete(result):
            def apply():
                if self.closed:
                    return False
                try:
                    value=result.result()
                except (OSError,ValueError) as error:
                    self.status.set_label(str(error));self.set_busy(False)
                else:
                    callback(value)
                return False
            GLib.idle_add(apply)
        future.add_done_callback(complete)

    def open_path(self,path):
        path=Path(path)
        self.set_busy(True);self.status.set_label("Opening document…")
        def loaded(data):
            def applied(_):
                self.path=path;self.update_title();self.set_busy(False);self.focus_document()
                self.status.set_label(f'{data["omitted"]} unavailable image(s) omitted' if data["omitted"] else "Document opened")
            self.js("window.editor.loadHTML("+json.dumps(data["html"])+")",applied)
        self.work(lambda:read_html(path),loaded)

    def save_to(self,path):
        path=Path(path)
        self.set_busy(True);self.status.set_label("Saving document…")
        def exported(snapshot):
            def written(_):
                if self.state.get("documentId")==snapshot["documentId"]:
                    self.path=path
                def marked(_):
                    self.set_busy(False);self.update_title();self.focus_document();self.status.set_label("Document saved")
                self.js(f'window.editor.markSaved({snapshot["documentId"]},{snapshot["revision"]})',marked)
            self.work(lambda:write_html(path,snapshot["html"]),written)
        self.js("window.editor.exportHTML()",exported)

    def save(self):
        if not self.file_busy:
            self.save_to(self.path) if self.path else self.file_dialog(True)

    def margin_controls(self,values,changed=None):
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,
            margin_top=18,margin_bottom=18,margin_start=18,margin_end=18)
        box.append(Gtk.Label(label="Margins in millimetres (0–90 mm)",xalign=0))
        spins={}
        for side in ("top","bottom","left","right"):
            row=Gtk.Box(spacing=16)
            row.append(Gtk.Label(label=side.capitalize(),hexpand=True,xalign=0))
            spin=Gtk.SpinButton.new_with_range(0,90,0.5);spin.set_digits(1)
            spin.set_value(values[side]);spins[side]=spin
            spin.update_property([Gtk.AccessibleProperty.LABEL],[side.capitalize()+" margin in millimetres"])
            row.append(spin);box.append(row)
        if changed:
            for spin in spins.values():
                spin.connect("value-changed",lambda *_:changed({side:widget.get_value() for side,widget in spins.items()}))
        return box,spins

    def show_margins(self):
        def loaded(values):
            dialog=Gtk.Dialog(title="Page margins",transient_for=self,modal=True)
            dialog.add_button("Cancel",Gtk.ResponseType.CANCEL)
            dialog.add_button("Apply",Gtk.ResponseType.OK)
            box,spins=self.margin_controls(values)
            dialog.get_content_area().append(box)
            def response(dialog,response):
                if response==Gtk.ResponseType.OK:
                    values={side:spin.get_value() for side,spin in spins.items()}
                    self.js("window.editor.setMargins("+json.dumps(values)+")")
                dialog.destroy();GLib.idle_add(self.focus_document)
            dialog.connect("response",response);dialog.present()
        self.js("window.editor.getMargins()",loaded)

    def create_print_operation(self):
        operation=WebKit.PrintOperation.new(self.webview)
        page=Gtk.PageSetup();page.set_paper_size(Gtk.PaperSize.new(Gtk.PAPER_NAME_A4))
        for side in ("top","bottom","left","right"):
            getattr(page,"set_"+side+"_margin")(getattr(self,"document_margins",{}).get(side,20),Gtk.Unit.MM)
        self.configure_print_page(operation,page)
        operation.connect("failed",lambda _,error:self.status.set_label("Printing failed: "+error.message))
        operation.connect("finished",lambda _:self.status.set_label("Print operation finished"))
        return operation

    def configure_print_page(self,operation,page):
        operation.set_page_setup(page)
        width=page.get_paper_width(Gtk.Unit.MM)-page.get_left_margin(Gtk.Unit.MM)-page.get_right_margin(Gtk.Unit.MM)
        height=page.get_paper_height(Gtk.Unit.MM)-page.get_top_margin(Gtk.Unit.MM)-page.get_bottom_margin(Gtk.Unit.MM)
        # WebKitGTK's print context uses 90 CSS pixels per physical inch.
        self.js("Object.assign(document.documentElement.dataset,"+json.dumps({"printWidth":str(max(1,width)*90/25.4),"printHeight":str(max(1,height)*90/25.4)})+")")

    def print_document(self,preview=False):
        if not self.state.get("ready"):return
        def loaded(values):
            self.document_margins=values
            self.open_print_dialog()
            if preview:self.select_preview_tab()
        self.js("window.editor.getMargins()",loaded)

    def open_print_dialog(self):
        if not self.state.get("ready"):return
        if getattr(self,"print_dialog",None):
            self.print_dialog.present();return
        dialog=Gtk.PrintUnixDialog(title="Print",transient_for=self,modal=True)
        self.print_dialog=dialog
        operation=self.create_print_operation()
        dialog.set_page_setup(operation.get_page_setup());dialog.set_embed_page_setup(True)
        dialog.set_default_size(850,720)
        self.print_preview=PrintPreview(self,dialog)
        dialog.add_custom_tab(self.print_preview.box,Gtk.Label(label="Preview"))
        syncing_margins=False
        def changed(values):
            if syncing_margins:return
            page=dialog.get_page_setup().copy()
            for side,value in values.items():getattr(page,"set_"+side+"_margin")(value,Gtk.Unit.MM)
            dialog.set_page_setup(page)
        margins,self.print_margin_spins=self.margin_controls(self.document_margins,changed)
        dialog.add_custom_tab(margins,Gtk.Label(label="Margins"))
        def sync_margins(*_):
            nonlocal syncing_margins
            syncing_margins=True
            try:
                page=dialog.get_page_setup()
                for side,spin in self.print_margin_spins.items():
                    value=getattr(page,"get_"+side+"_margin")(Gtk.Unit.MM)
                    if abs(spin.get_value()-value)>0.05:spin.set_value(value)
            finally:syncing_margins=False
        dialog.connect("notify::page-setup",sync_margins)
        def response(dialog,response):
            if response==Gtk.ResponseType.OK:
                self.print_operation=self.create_print_operation()
                self.configure_print_page(self.print_operation,dialog.get_page_setup())
                self.print_operation.set_print_settings(dialog.get_settings())
                self.print_operation.print_()
            self.print_preview.close();self.print_dialog=None;dialog.destroy()
            GLib.idle_add(self.focus_document)
        dialog.connect("response",response);dialog.present()

    def show_print_preview(self):
        self.print_document(preview=True)

    def select_preview_tab(self):
        if not getattr(self,"print_dialog",None):return
        def descendants(widget):
            yield widget;child=widget.get_first_child()
            while child:
                yield from descendants(child);child=child.get_next_sibling()
        for widget in descendants(self.print_dialog):
            if isinstance(widget,Gtk.Notebook):
                for index in range(widget.get_n_pages()):
                    page=widget.get_nth_page(index)
                    if page is self.print_preview.box or self.print_preview.box.is_ancestor(page):
                        widget.set_current_page(index);return

    def guard_discard(self,action):
        if self.file_busy:
            self.status.set_label("Please wait for the file operation to finish.");return
        # Ask the live editor, rather than trusting a debounced dirty-state message.
        def inspected(state):
            if not state["dirty"]:
                action();return
            dialog=Adw.MessageDialog(transient_for=self,heading="Discard unsaved changes?",body="Save your document before discarding changes.")
            dialog.add_response("cancel","Cancel");dialog.add_response("discard","Discard")
            dialog.set_response_appearance("discard",Adw.ResponseAppearance.DESTRUCTIVE)
            dialog.set_default_response("cancel");dialog.set_close_response("cancel")
            dialog.connect("response",lambda _,r:action() if r=="discard" else self.focus_document())
            dialog.present()
        if self.state.get("ready"):
            self.js("window.editor.getSummary()",inspected)

    def new(self):
        def create():
            def done(_):
                self.path=None;self.update_title();self.focus_document()
            self.js('window.editor.loadHTML("<p></p>")',done)
        self.guard_discard(create)

    def file_dialog(self,saving):
        if saving:
            if not self.file_busy:self.choose_file(True)
        else:self.guard_discard(lambda:self.choose_file(False))

    def styled_file_chooser(self,title,action,accept):
        if self.sandboxed:
            return Gtk.FileChooserNative(title=title,transient_for=self,modal=True,
                action=action,accept_label=accept,cancel_label="Cancel")
        dialog=Gtk.FileChooserDialog(title=title,transient_for=self,modal=True,action=action)
        dialog.add_buttons("Cancel",Gtk.ResponseType.CANCEL,accept,Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT).add_css_class("suggested-action")
        dialog.set_default_size(900,650)
        return dialog

    def choose_file(self,saving):
        dialog=self.styled_file_chooser("Save HTML" if saving else "Open HTML",
            Gtk.FileChooserAction.SAVE if saving else Gtk.FileChooserAction.OPEN,"Save" if saving else "Open")
        self.file_chooser=dialog
        filter=Gtk.FileFilter(name="HTML documents")
        filter.add_pattern("*.html");filter.add_pattern("*.htm");filter.add_pattern("*.HTML")
        dialog.add_filter(filter)
        if saving:dialog.set_current_name(self.path.name if self.path else "Untitled.html")
        def response(chooser,result):
            if result==Gtk.ResponseType.ACCEPT:
                selected=chooser.get_file();selected_path=selected.get_path() if selected else None
                if selected_path:
                    path=Path(selected_path)
                    if saving and not path.suffix and not self.sandboxed:path=path.with_suffix(".html")
                    self.save_to(path) if saving else self.open_path(path)
                else:self.status.set_label("Choose a locally accessible HTML file.")
            chooser.destroy();self.file_chooser=None
            GLib.idle_add(self.focus_document)
        dialog.connect("response",response);dialog.show()

    def image_dialog(self):
        if self.state.get("image"):
            image_size_dialog(self,self.state["image"]);return
        if self.image_chooser:
            self.image_chooser.show();return
        # Use the desktop's native/portal picker for image thumbnail browsing,
        # rather than forcing the app-styled legacy GTK list chooser.
        dialog=Gtk.FileChooserNative(title="Insert image",transient_for=self,modal=True,
            action=Gtk.FileChooserAction.OPEN,accept_label="Insert",cancel_label="Cancel")
        self.image_chooser=dialog
        filter=Gtk.FileFilter(name="PNG, JPEG, GIF or WebP")
        for mime in ("image/png","image/jpeg","image/gif","image/webp"):filter.add_mime_type(mime)
        dialog.add_filter(filter)
        def response(chooser,result):
            if result==Gtk.ResponseType.ACCEPT:
                selected=chooser.get_file();path=selected.get_path() if selected else None
                if path:self.work(lambda:image_uri(path),lambda src:self.command("image",{"src":src,"alt":Path(path).name}))
                else:self.status.set_label("Choose a locally accessible image file.")
            chooser.destroy();self.image_chooser=None;GLib.idle_add(self.focus_document)
        dialog.connect("response",response);dialog.show()

    def link_dialog(self):
        dialog=Adw.MessageDialog(transient_for=self,heading="Insert link",body="Web or email address.")
        compact_dialog(dialog)
        self.link_window=dialog
        entry=Gtk.Entry(placeholder_text="https://example.org")
        dialog.set_extra_child(entry);dialog.add_response("cancel","Cancel");dialog.add_response("insert","Insert")
        dialog.set_response_appearance("insert",Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("insert");dialog.set_close_response("cancel")
        def response(_,answer):
            value=entry.get_text();dialog.destroy();self.link_window=None
            self.command("link",{"value":value}) if answer=="insert" else self.focus_document()
        dialog.connect("response",response)
        dialog.present();entry.grab_focus()

    def navigation(self,view,decision,kind):
        if kind==WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            if decision.get_navigation_action().get_request().get_uri()!=(ROOT/"editor.html").as_uri():
                decision.ignore();return True
        if kind==WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
            decision.ignore();return True
        return False

    def load_failed(self,view,event,uri,error):
        self.status.set_label("Editor failed to load: "+error.message);return False

    def web_terminated(self,view,reason):
        self.state["ready"]=False
        self.set_busy(False)
        self.tools.set_sensitive(False);self.status.set_label("The editor process stopped. Unsaved changes may be lost.")

    def on_close(self,*_):
        if self.closed:return False
        if self.file_busy:
            self.status.set_label("Please wait for the file operation to finish.");return True
        if not self.discard_confirmed and self.state.get("ready"):
            def close():
                self.discard_confirmed=True;self.close()
            self.guard_discard(close);return True
        self.closed=True
        self.outline.dispose()
        if self.preference_timer:
            GLib.source_remove(self.preference_timer);self.save_appearance()
        if self.interface_window:self.interface_window.destroy()
        if self.about_window:self.about_window.destroy();self.about_window=None
        if self.image_chooser:self.image_chooser.destroy();self.image_chooser=None
        if getattr(self,"table_window",None):self.table_window.destroy()
        if getattr(self,"textbox_window",None):self.textbox_window.destroy()
        if getattr(self,"print_dialog",None):self.print_dialog.response(Gtk.ResponseType.CANCEL)
        if self.frame_handler:
            self.frame_clock.disconnect(self.frame_handler);self.frame_handler=None
        Gtk.StyleContext.remove_provider_for_display(self.get_display(),self.css)
        self.executor.shutdown(wait=False,cancel_futures=True)
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.paullinux_gn.WebkitGN",flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        window=self.get_active_window()
        if not window:window=Editor(self)
        window.present()


if __name__=="__main__":
    sys.exit(App().run(sys.argv))
