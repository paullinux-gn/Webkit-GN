"""Shared toolbar-style surfaces for all GTK menus and auxiliary windows."""

def surface_css(dark,opacity,native_blur,blur_radius,blur):
    rgb="37,39,45" if dark else "250,250,252"
    ink="#f2f3f5" if dark else "#202124"
    # Separate GTK surfaces cannot use the document's WebKit backdrop fallback.
    # Keep them opaque on GTK versions without native backdrop filtering.
    tint=opacity if native_blur and blur else 1
    backdrop=f"backdrop-filter:blur({blur_radius}px);" if native_blur and blur else ""
    return f"""
    @define-color wp_surface rgba({rgb},{tint});
    @define-color wp_surface_ink {ink};
    popover {{ background:transparent; border:0; box-shadow:none; }}
    popover > contents {{ background:@wp_surface; background-image:none;
      color:@wp_surface_ink; border:1px solid alpha(@wp_surface_ink,.10);
      border-radius:14px; box-shadow:0 3px 8px alpha(black,.15); padding:6px; {backdrop} }}
    popover > arrow {{ background:@wp_surface; border-color:alpha(@wp_surface_ink,.10); }}
    popover listview, popover list, popover scrolledwindow, popover viewport {{ background:transparent; color:@wp_surface_ink; }}
    popover label, popover image {{ color:inherit; }}
    popover button:not(.color-swatch), popover modelbutton {{ background:transparent;
      background-image:none; color:@wp_surface_ink; border:1px solid transparent;
      border-radius:6px; box-shadow:none; font-weight:400; }}
    popover button:not(.color-swatch):hover, popover modelbutton:hover,
    popover listview > row:hover {{ background:alpha(@wp_surface_ink,.07); }}
    popover button:not(.color-swatch):checked, popover modelbutton:checked,
    popover listview > row:selected {{ background:alpha(@accent_bg_color,.18); color:@accent_color; }}
    popover label {{ font-weight:400; }}
    popover separator {{ background:alpha(@wp_surface_ink,.12); border:0;
      box-shadow:none; min-height:1px; margin:4px; }}
    popover entry {{ color:@wp_surface_ink; background:alpha(@wp_surface_ink,.05);
      border:1px solid alpha(@wp_surface_ink,.12); border-radius:8px; box-shadow:none; }}
    window:not(.wp-editor) {{ background:@wp_surface; background-image:none;
      color:@wp_surface_ink; border-radius:20px; {backdrop} }}
    window:not(.wp-editor) headerbar,
    window:not(.wp-editor) toolbarview > .top-bar,
    window:not(.wp-editor) .message-area,
    window:not(.wp-editor) .dialog-action-area,
    window:not(.wp-editor) preferencespage,
    window:not(.wp-editor) scrolledwindow,
    window:not(.wp-editor) viewport,
    window:not(.wp-editor) .view,
    window:not(.wp-editor) listview,
    window:not(.wp-editor) list {{ background:transparent; color:inherit; box-shadow:none; }}
    window:not(.wp-editor) headerbar {{ border:0; }}
    window:not(.wp-editor) button:not(.suggested-action):not(.destructive-action):not(.theme-choice):not(.color-swatch) {{
      background:transparent; background-image:none; color:inherit;
      border:1px solid transparent; border-radius:6px; box-shadow:none; font-weight:400; }}
    window:not(.wp-editor) button:not(.suggested-action):not(.destructive-action):not(.theme-choice):not(.color-swatch):hover {{
      background:alpha(@wp_surface_ink,.07); }}
    window:not(.wp-editor) button:not(.theme-choice):not(.color-swatch):checked {{
      background:alpha(@accent_bg_color,.18); color:@accent_color; }}
    window:not(.wp-editor) button.suggested-action,
    window:not(.wp-editor) button.destructive-action {{ border-radius:8px; font-weight:400; }}
    window:not(.wp-editor) entry, window:not(.wp-editor) spinbutton {{
      background:alpha(@wp_surface_ink,.05); color:inherit;
      border:1px solid alpha(@wp_surface_ink,.12); border-radius:8px; box-shadow:none; }}
    window:not(.wp-editor) spinbutton text {{ background:transparent; color:inherit; }}
    window:not(.wp-editor) list.boxed-list {{ background:alpha(@wp_surface_ink,.04);
      border:1px solid alpha(@wp_surface_ink,.10); border-radius:12px; box-shadow:none; }}
    window:not(.wp-editor) list > row:hover {{ background:alpha(@wp_surface_ink,.07); }}
    window:not(.wp-editor) list > row:selected {{ background:alpha(@accent_bg_color,.18); }}
    window:not(.wp-editor) separator {{ background:alpha(@wp_surface_ink,.12);
      border:0; box-shadow:none; }}
    popover.compact-action-menu > contents {{ padding:4px; }}
    popover.compact-action-menu modelbutton {{ min-height:22px; padding:3px 8px; }}
    popover.compact-action-menu separator {{ margin:2px 3px; }}
    popover.compact-menu > contents {{ padding:3px; border-radius:10px; }}
    popover.compact-menu button, popover.compact-menu checkbutton {{
      min-height:22px; padding:2px 6px; margin:0; }}
    window.compact-editor-dialog .message-area {{ padding:14px 16px 10px; border-spacing:10px; }}
    window.compact-editor-dialog .heading {{ font-size:1.1em; }}
    window.compact-editor-dialog .response-area {{ padding:0 16px 14px; border-spacing:6px; }}
    window.compact-editor-dialog .response-area button {{ min-height:26px; min-width:60px; padding:2px 10px; }}
    window.compact-editor-dialog .extra-child bin {{ margin:0; }}
    window.compact-editor-dialog entry,
    window.compact-editor-dialog spinbutton {{ min-height:26px; }}
    window.compact-editor-dialog dropdown > button,
    window.compact-editor-dialog spinbutton button {{ min-height:22px; min-width:20px; padding:2px 4px; }}
    """


def compact_dialog(dialog):
    """Keep small editor prompts and their response buttons tightly sized."""
    from gi.repository import Gtk
    dialog.add_css_class("compact-editor-dialog")
    def layout(widget):
        if widget.has_css_class("response-area"):
            widget.set_halign(Gtk.Align.END)
            if isinstance(widget,Gtk.Box):widget.set_homogeneous(False)
        child=widget.get_first_child()
        while child:layout(child);child=child.get_next_sibling()
    dialog.connect("map",lambda *_:layout(dialog))
