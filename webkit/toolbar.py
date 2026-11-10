"""Grouped native text controls. All edits are delegated to ProseMirror."""
from pathlib import Path
import re
from gi.repository import Gtk,Adw,Gio,Gdk
from ui_surfaces import compact_dialog

ROOT=Path(__file__).resolve().parent
# Use Twinly's GNOME symbolic names so icons follow the installed theme.
THEMED_ICONS={
    "bold":"format-text-bold-symbolic", "italic":"format-text-italic-symbolic",
    "underline":"format-text-underline-symbolic", "strike":"format-text-strikethrough-symbolic",
    "color":"color-select-symbolic", "highlight":"document-edit-symbolic",
    "checklist":"checkbox-checked-symbolic", "bullets":"view-list-bullet-symbolic", "numbered":"view-list-ordered-symbolic",
    "lift":"edit-delete-symbolic", "clear":"edit-clear-symbolic",
    "photo":"insert-image-symbolic", "link":"insert-link-symbolic",
    "table":"view-grid-symbolic", "textbox":"insert-text-symbolic",
    "horizontalRule":"list-remove-symbolic", "print":"document-print-symbolic",
    "printPreview":"document-print-preview-symbolic", "findReplace":"edit-find-replace-symbolic", "outline":"view-list-symbolic", "columns":"view-dual-symbolic",
    "undo":"edit-undo-symbolic", "redo":"edit-redo-symbolic",
    **{"align-"+value:"format-justify-"+("fill" if value=="justify" else value)+"-symbolic"
       for value in ("left","center","right","justify")},
}
from colours import TEXT_COLOURS,HIGHLIGHT_COLOURS,COLOUR_FAMILIES,palette_positions


def icon(name):
    if name=="pageBreak":
        display=Gdk.Display.get_default()
        if display and Gtk.IconTheme.get_for_display(display).has_icon("insert-page-break-symbolic"):
            return Gio.ThemedIcon.new("insert-page-break-symbolic")
    if name=="lineSpacing":
        display=Gdk.Display.get_default()
        if display and Gtk.IconTheme.get_for_display(display).has_icon("format-line-spacing-symbolic"):
            return Gio.ThemedIcon.new("format-line-spacing-symbolic")
    if name in THEMED_ICONS:return Gio.ThemedIcon.new(THEMED_ICONS[name])
    return Gio.FileIcon.new(Gio.File.new_for_path(str(ROOT/"icons"/(name+"-symbolic.svg"))))


def image(name):
    result=Gtk.Image.new_from_gicon(icon(name));result.set_pixel_size(16)
    return result


def group(row):
    if row.get_first_child():
        divider=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL,margin_top=4,margin_bottom=4)
        divider.add_css_class("toolbar-divider");row.append(divider)
    box=Gtk.Box(spacing=1);box.add_css_class("toolbar-group");row.append(box)
    return box


def action_button(editor,box,command,tooltip,toggle=False):
    button=(Gtk.ToggleButton if toggle else Gtk.Button)(focus_on_click=False,tooltip_text=tooltip)
    button.update_property([Gtk.AccessibleProperty.LABEL],[tooltip])
    button.set_child(image(command))
    button.connect("clicked",lambda _:editor.command(command))
    box.append(button);editor.action_buttons[command]=button
    if toggle:editor.toggle_buttons[command]=button
    return button


def icon_menu(box,name,tooltip):
    button=Gtk.MenuButton(tooltip_text=tooltip)
    button.update_property([Gtk.AccessibleProperty.LABEL],[tooltip])
    child=Gtk.Box(spacing=3);picture=image(name);child.append(picture)
    child.append(Gtk.Image.new_from_icon_name("pan-down-symbolic"));button.set_child(child)
    box.append(button)
    return button,picture


def apply_and_close(editor,menu,command,args):
    menu.popdown();editor.command(command,args)


def colour_menu(editor,box,command,tooltip):
    menu,_=icon_menu(box,command,tooltip)
    popover=Gtk.Popover(has_arrow=False);palette=Gtk.Grid(row_spacing=5,column_spacing=5,margin_top=10,margin_bottom=10,margin_start=10,margin_end=10)
    editor.palette_buttons[command]={}
    colours=HIGHLIGHT_COLOURS if command=="highlight" else TEXT_COLOURS
    positions=palette_positions(colours)
    last_row=max(row for _,row in positions.values())
    for index,(name,value) in enumerate((*colours,("Remove colour",None))):
        button=Gtk.Button(tooltip_text=name,focus_on_click=False)
        button.add_css_class("color-swatch");button.add_css_class("swatch-clear" if value is None else "swatch-"+str(index))
        button.update_property([Gtk.AccessibleProperty.LABEL],[name])
        button.connect("clicked",lambda _,colour=value:apply_and_close(editor,menu,command,{"value":colour}))
        column,row=positions[name] if value is not None else (len(COLOUR_FAMILIES)-1,last_row+1)
        palette.attach(button,column,row,1,1);editor.palette_buttons[command][value]=button
    popover.set_child(palette);menu.set_popover(popover)
    return menu


def searchable_fonts(names):
    dropdown=Gtk.DropDown.new_from_strings(names)
    # GTK needs an expression to extract searchable text from Gtk.StringObject.
    dropdown.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject,None,"string"))
    dropdown.set_enable_search(True)
    dropdown.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
    return dropdown


def build_text_toolbar(editor):
    row=Gtk.Box(spacing=4,hexpand=True)
    controls=Gtk.Box(spacing=4)
    row.append(Gtk.Box(hexpand=True));row.append(controls);row.append(Gtk.Box(hexpand=True))
    typography=group(controls)
    editor.styles=Gtk.MenuButton(label="Normal",tooltip_text="Paragraph styles")
    editor.styles.set_always_show_arrow(True);typography.append(editor.styles)
    editor.style_popover=Gtk.Popover(has_arrow=False);editor.style_popover.add_css_class("compact-menu")
    editor.style_rows=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0,
        margin_top=3,margin_bottom=3,margin_start=3,margin_end=3)
    style_scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        max_content_height=360,propagate_natural_height=True)
    style_scroll.set_child(editor.style_rows);editor.style_popover.set_child(style_scroll);editor.styles.set_popover(editor.style_popover)
    families=editor.get_pango_context().get_font_map().list_families()
    editor.font_names=["Sans","Serif","Monospace"]+sorted({f.get_name() for f in families}-{ "Sans","Serif","Monospace"})
    editor.fonts=searchable_fonts(editor.font_names)
    editor.fonts.set_size_request(145,-1)
    editor.fonts.set_tooltip_text("Font")
    editor.fonts.connect("notify::selected",lambda widget,_:None if editor.syncing else editor.command("font",{"value":editor.font_names[widget.get_selected()]}))
    typography.append(editor.fonts)
    editor.size_values=["8","9","10","11","12","14","16","18","20","24","28","32","36","48","60","72"]
    editor.size=Gtk.DropDown.new_from_strings(editor.size_values);editor.size.set_selected(4)
    editor.size.set_tooltip_text("Font size")
    editor.size.connect("notify::selected",lambda widget,_:None if editor.syncing else editor.command("size",{"value":float(editor.size_values[widget.get_selected()])}))
    typography.append(editor.size)
    marks=group(controls)
    for command,title in (("bold","Bold"),("italic","Italic"),("underline","Underline"),("strike","Strikethrough")):
        action_button(editor,marks,command,title,True)
    scripts=group(controls)
    for command,title in (("subscript","Subscript"),("superscript","Superscript")):
        action_button(editor,scripts,command,title,True)
    searching=group(controls)
    editor.find_button=Gtk.ToggleButton(focus_on_click=False,tooltip_text="Search and replace (Ctrl+H)")
    editor.find_button.update_property([Gtk.AccessibleProperty.LABEL],["Search and replace"])
    editor.find_button.set_child(image("findReplace"))
    editor.find_button.connect("toggled",lambda button:editor.search.show() if button.get_active() else editor.search.hide())
    searching.append(editor.find_button)
    divider=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL,margin_top=4,margin_bottom=4)
    divider.add_css_class("toolbar-divider");row.append(divider)
    outline_group=Gtk.Box();outline_group.add_css_class("toolbar-group");row.append(outline_group)
    editor.outline_button=Gtk.ToggleButton(focus_on_click=False,tooltip_text="Document outline (Ctrl+Shift+O)")
    editor.outline_button.update_property([Gtk.AccessibleProperty.LABEL],["Document outline"])
    editor.outline_button.set_child(image("outline"))
    editor.outline_button.connect("toggled",lambda button:editor.outline.show() if button.get_active() else editor.outline.hide())
    outline_group.append(editor.outline_button)
    return row


def build_action_toolbar(editor):
    row=Gtk.Box(spacing=4)
    lists=group(row)
    for command,title in (("bullets","Bulleted list"),("numbered","Numbered list"),("checklist","Checklist"),("lift","Decrease indent / unwrap")):
        action_button(editor,lists,command,title,command=="checklist")
    alignment=group(row)
    editor.alignment_menu,editor.alignment_image=icon_menu(alignment,"align-justify","Alignment")
    popover=Gtk.Popover(has_arrow=False);popover.add_css_class("compact-menu")
    options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0,
        margin_top=2,margin_bottom=2,margin_start=2,margin_end=2)
    editor.alignment_buttons={}
    for value,label in (("left","Align left"),("center","Center"),("right","Align right"),("justify","Justify")):
        button=Gtk.Button();content=Gtk.Box(spacing=6);content.append(image("align-"+value));content.append(Gtk.Label(label=label))
        button.set_child(content);button.add_css_class("flat")
        button.connect("clicked",lambda _,alignment=value:apply_and_close(editor,editor.alignment_menu,"align",{"value":alignment}))
        options.append(button);editor.alignment_buttons[value]=button
    popover.set_child(options);editor.alignment_menu.set_popover(popover)
    editor.line_spacing_menu,_=icon_menu(alignment,"lineSpacing","Line spacing")
    spacing_popover=Gtk.Popover(has_arrow=False);spacing_popover.add_css_class("compact-menu")
    spacing_options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0,
        margin_top=4,margin_bottom=4,margin_start=4,margin_end=4)
    editor.line_spacing_buttons={};first=None
    for value,label in ((.95,"0.95"),(1,"Single (1.0)"),(1.15,"1.15"),(1.5,"1.5"),(2,"Double (2.0)"),(2.5,"2.5"),(3,"3.0")):
        choice=Gtk.CheckButton(label=label)
        if first:choice.set_group(first)
        else:first=choice
        choice.connect("toggled",lambda button,amount=value:
            apply_and_close(editor,editor.line_spacing_menu,"lineSpacing",{"value":amount}) if button.get_active() and not editor.syncing else None)
        spacing_options.append(choice);editor.line_spacing_buttons[value]=choice
    spacing_popover.set_child(spacing_options);editor.line_spacing_menu.set_popover(spacing_popover)
    editor.columns_menu,_=icon_menu(alignment,"columns","Document columns")
    column_popover=Gtk.Popover(has_arrow=False);column_popover.add_css_class("compact-menu")
    column_options=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=0)
    editor.column_buttons={};first=None
    for count in (1,2,3):
        choice=Gtk.CheckButton(label=f"{count} column"+('s' if count!=1 else ''))
        if first:choice.set_group(first)
        else:first=choice
        choice.connect("toggled",lambda button,value=count:
            apply_and_close(editor,editor.columns_menu,"columns",{"value":value}) if button.get_active() and not editor.syncing else None)
        column_options.append(choice);editor.column_buttons[count]=choice
    column_popover.set_child(column_options);editor.columns_menu.set_popover(column_popover)
    colours=group(row);editor.palette_buttons={};editor.color_menus={}
    for command,title in (("color","Text colour"),("highlight","Highlight colour")):
        editor.color_menus[command]=colour_menu(editor,colours,command,title)
    insert=group(row)
    for name,title,callback in (
            ("photo","Insert image",editor.image_dialog),
            ("table","Insert table",lambda:table_dialog(editor)),
            ("link","Insert link",editor.link_dialog),
            ("textbox","Insert text box",lambda:textbox_dialog(editor)),
            ("horizontalRule","Insert horizontal line",lambda:editor.command("horizontalRule")),
            ("pageBreak","Insert page break (Ctrl+Enter)",lambda:editor.command("pageBreak"))):
        button=Gtk.Button(focus_on_click=False,tooltip_text=title)
        button.update_property([Gtk.AccessibleProperty.LABEL],[title])
        button.set_child(image(name));button.connect("clicked",lambda _,fn=callback:fn())
        insert.append(button);editor.action_buttons[name]=button
    history=group(row)
    for command,title in (("clear","Remove text formatting"),("undo","Undo"),("redo","Redo")):
        action_button(editor,history,command,title)
    printing=group(row)
    editor.preview_button=Gtk.Button(focus_on_click=False,tooltip_text="Print preview (Ctrl+Shift+P)")
    editor.preview_button.update_property([Gtk.AccessibleProperty.LABEL],["Print preview"])
    editor.preview_button.set_child(image("printPreview"));editor.preview_button.connect("clicked",lambda _:editor.show_print_preview())
    printing.append(editor.preview_button)
    editor.print_button=Gtk.Button(focus_on_click=False,tooltip_text="Print (Ctrl+P)")
    editor.print_button.update_property([Gtk.AccessibleProperty.LABEL],["Print"])
    editor.print_button.set_child(image("print"));editor.print_button.connect("clicked",lambda _:editor.print_document())
    printing.append(editor.print_button)
    return row


def refresh_styles(editor,styles):
    if getattr(editor,"known_styles",None)==styles:return
    editor.known_styles=styles
    child=editor.style_rows.get_first_child()
    while child:
        next_child=child.get_next_sibling();editor.style_rows.remove(child);child=next_child
    editor.style_buttons={}
    for heading in (False,True):
        label=Gtk.Label(label="Headings" if heading else "Body",xalign=0)
        label.add_css_class("dim-label");label.set_margin_start(8);editor.style_rows.append(label)
        for name,preset in styles.items():
            if bool(preset["level"])!=heading:continue
            button=Gtk.Button(label=name);button.add_css_class("flat")
            button.connect("clicked",lambda _,style=name:apply_and_close(editor,editor.styles,"style",{"name":style}))
            editor.style_rows.append(button);editor.style_buttons[name]=button
    editor.style_rows.append(Gtk.Separator())
    for title,handler in (("Edit current style…",lambda:style_dialog(editor,False)),("New style…",lambda:style_dialog(editor,True))):
        button=Gtk.Button(label=title);button.add_css_class("flat")
        button.connect("clicked",lambda _,fn=handler:(editor.styles.popdown(),fn()))
        editor.style_rows.append(button)


def sync_text_toolbar(editor,state):
    editor.action_buttons["photo"].set_tooltip_text("Picture size (or double-click picture)" if state.get("image") else "Insert image")
    editor.action_buttons["table"].set_tooltip_text("Table properties" if state.get("table") else "Insert table")
    editor.action_buttons["textbox"].set_tooltip_text("Text box properties" if state.get("textbox") else "Insert text box")
    refresh_styles(editor,state["styles"])
    fmt=state["format"];editor.styles.set_label(fmt["style"])
    for count,button in editor.column_buttons.items():button.set_active(count==fmt.get("columns",1))
    spacing=fmt.get("lineSpacing",1.5)
    editor.line_spacing_menu.set_tooltip_text(f"Line spacing: {spacing:g}")
    for value,button in editor.line_spacing_buttons.items():button.set_active(abs(value-spacing)<.001)
    font=fmt["font"].strip("\"'")
    alias={"sans-serif":"Sans","sans":"Sans","serif":"Serif","monospace":"Monospace"}
    font=alias.get(font.lower(),font)
    if font not in editor.font_names:editor.font_names.append(font);editor.fonts.get_model().append(font)
    editor.fonts.set_selected(editor.font_names.index(font))
    try:
        value=float(fmt["size"].removesuffix("pt").removesuffix("px"))
        if fmt["size"].endswith("px"):value*=.75
        size=f"{value:g}"
        if size not in editor.size_values:editor.size_values.append(size);editor.size.get_model().append(size)
        editor.size.set_selected(editor.size_values.index(size))
    except ValueError:pass


def style_dialog(editor,create):
    current=editor.state["format"]["style"]
    styles=editor.state["styles"]
    preset=styles.get(current,styles["Normal"])
    types=[("Body",0,"Normal"),("Title",1,"Title"),("H1",1,"H1"),("H2",2,"H2"),("H3",3,"H3")]
    builtin=current in ("Normal","Title","H1","H2","H3")
    category=preset.get("kind",("Title" if current=="Title" else "H"+str(preset["level"]) if preset["level"] else "Body"))
    initial=next(i for i,item in enumerate(types) if item[0]==category)
    if create:
        fmt=editor.state["format"];number=float(fmt["size"].removesuffix("pt").removesuffix("px"))
        preset={**preset,"font":fmt["font"],"size":number*(.75 if fmt["size"].endswith("px") else 1),
                "bold":fmt["strong"],"italic":fmt["em"]}
    dialog=Adw.MessageDialog(transient_for=editor,heading="New paragraph style" if create else "Edit “"+current+"”")
    compact_dialog(dialog)
    editor.style_dialog=dialog
    grid=Gtk.Grid(row_spacing=8,column_spacing=10)
    defaults={"Body":"Custom body","Title":"Custom title","H1":"Custom H1","H2":"Custom H2","H3":"Custom H3"}
    name=Gtk.Entry(text=defaults[category] if create else current,editable=create or not builtin)
    if not create and builtin:name.set_tooltip_text("Create a custom style to choose a different name")
    if preset["font"] not in editor.font_names:
        editor.font_names.append(preset["font"]);editor.fonts.get_model().append(preset["font"])
    fonts=searchable_fonts(editor.font_names)
    fonts.set_selected(editor.font_names.index(preset["font"]))
    size=Gtk.SpinButton.new_with_range(6,144,.5);size.set_value(preset["size"])
    kind=Gtk.DropDown.new_from_strings([item[0] for item in types]);kind.set_selected(initial)
    kind.set_sensitive(create or not builtin)
    bold=Gtk.CheckButton(label="Bold",active=preset["bold"]);italic=Gtk.CheckButton(label="Italic",active=preset["italic"])
    for row,(label,control) in enumerate((("Name",name),("Font",fonts),("Font size",size),("Type",kind))):
        grid.attach(Gtk.Label(label=label,xalign=0),0,row,1,1);grid.attach(control,1,row,1,1)
    grid.attach(bold,0,4,1,1);grid.attach(italic,1,4,1,1)
    validation=Gtk.Label(xalign=0,wrap=True);validation.add_css_class("error");grid.attach(validation,0,5,2,1)
    dialog.set_extra_child(grid);dialog.add_response("cancel","Cancel");dialog.add_response("save","Create" if create else "Apply")
    dialog.set_response_appearance("save",Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("save");dialog.set_close_response("cancel")
    def validate(*_):
        value=name.get_text().strip()
        valid=bool(re.fullmatch(r"[\w -]{1,40}",value)) and value not in ("__proto__","constructor","prototype")
        collision=value in styles and (create or value!=current)
        message="A style with this name already exists." if collision else "Use 1–40 letters, numbers, spaces, dashes or underscores." if not valid else ""
        validation.set_text(message);validation.set_visible(bool(message));dialog.set_response_enabled("save",valid and not collision)
    def category_changed(*_):
        if not create:return
        category,_,base=types[kind.get_selected()];base_style=styles[base]
        if base_style["font"] not in editor.font_names:
            editor.font_names.append(base_style["font"]);editor.fonts.get_model().append(base_style["font"]);fonts.get_model().append(base_style["font"])
        fonts.set_selected(editor.font_names.index(base_style["font"]));size.set_value(base_style["size"])
        bold.set_active(base_style["bold"]);italic.set_active(base_style["italic"])
        if name.get_text() in defaults.values():name.set_text(defaults[category])
    name.connect("changed",validate);kind.connect("notify::selected",category_changed);validate()
    editor.style_controls={"name":name,"font":fonts,"size":size,"kind":kind,"bold":bold,"italic":italic}
    def response(_,answer):
        category,level,_=types[kind.get_selected()]
        args={"name":name.get_text().strip(),"preset":{"kind":category,"level":level,
            "font":editor.font_names[fonts.get_selected()],"size":size.get_value(),
            "bold":bold.get_active(),"italic":italic.get_active()}}
        if create:args["create"]=True
        else:args["oldName"]=current
        dialog.destroy();editor.style_dialog=None
        if answer=="save":editor.command("defineStyle",args)
        else:editor.focus_document()
    dialog.connect("response",response);dialog.present()


def table_dialog(editor,current=None):
    if getattr(editor,"table_window",None):editor.table_window.present();return
    current=current or editor.state.get("table")
    editing=bool(current)
    dialog=Adw.MessageDialog(transient_for=editor,heading="Table properties" if editing else "Insert table")
    compact_dialog(dialog)
    editor.table_window=dialog
    grid=Gtk.Grid(row_spacing=8,column_spacing=16)
    rows=Gtk.SpinButton.new_with_range(1,100,1);rows.set_value(3)
    columns=Gtk.SpinButton.new_with_range(1,20,1);columns.set_value(3)
    header=Gtk.CheckButton(label="Include header row",active=True)
    border=Gtk.SpinButton.new_with_range(0,12,1);border.set_value(1)
    widths=[25,50,75,100]
    width=Gtk.DropDown.new_from_strings([str(value)+"%" for value in widths]);width.set_selected(3)
    floating=Gtk.CheckButton(label="Free-floating (text wraps around)")
    floating.set_tooltip_text("Float the table to the left; following text flows beside it when space permits")
    for row,label,control in ((0,"Rows:",rows),(1,"Columns:",columns),(3,"Border width:",border),(4,"Table width:",width)):
        grid.attach(Gtk.Label(label=label,xalign=0,hexpand=True),0,row,1,1)
        control.update_property([Gtk.AccessibleProperty.LABEL],[label.rstrip(":")])
        if isinstance(control,Gtk.SpinButton):control.set_width_chars(2)
        grid.attach(control,1,row,1,1)
    grid.attach(header,0,2,2,1);grid.attach(floating,0,5,2,1)
    if editing:
        rows.set_range(1,max(100,current["rows"]));columns.set_range(1,max(20,current["cols"]))
        rows.set_value(current["rows"]);columns.set_value(current["cols"]);header.set_active(current["header"])
        border.set_value(current["borderWidth"])
        if current["width"] not in widths:widths.append(current["width"]);width.get_model().append(str(current["width"])+"%")
        width.set_selected(widths.index(current["width"]));floating.set_active(current["floating"])
        if current.get("merged"):
            rows.set_sensitive(False);columns.set_sensitive(False)
            rows.set_tooltip_text("Split merged cells before changing the table dimensions")
            columns.set_tooltip_text("Split merged cells before changing the table dimensions")
        def warn(*_):
            shrinking=rows.get_value_as_int()<current["rows"] or columns.get_value_as_int()<current["cols"]
            dialog.set_body("Reducing the size removes cells and their contents from the bottom or right." if shrinking else "")
        rows.connect("value-changed",warn);columns.connect("value-changed",warn)
        editor.table_exit_button=Gtk.Button(label="Continue below table · Alt+Enter",tooltip_text="Move out of the table into a paragraph below it")
        editor.table_exit_button.connect("clicked",lambda _:dialog.response("leave"))
        grid.attach(editor.table_exit_button,0,6,2,1)
        editor.table_delete_button=Gtk.Button(label="Delete table",tooltip_text="Remove this table and its contents (undo with Ctrl+Z)")
        editor.table_delete_button.add_css_class("destructive-action")
        editor.table_delete_button.connect("clicked",lambda _:dialog.response("delete"))
        grid.attach(editor.table_delete_button,0,7,2,1)
    editor.table_controls={"rows":rows,"cols":columns,"header":header,"borderWidth":border,"width":width,"floating":floating}
    dialog.set_extra_child(grid);dialog.add_response("cancel","Cancel");dialog.add_response("insert","Apply" if editing else "Insert")
    dialog.set_response_appearance("insert",Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("insert");dialog.set_close_response("cancel")
    def response(_,answer):
        args={"rows":rows.get_value_as_int(),"cols":columns.get_value_as_int(),"header":header.get_active(),
            "borderWidth":border.get_value_as_int(),"width":widths[width.get_selected()],"floating":floating.get_active()}
        editor.table_window=None;dialog.destroy()
        if answer=="leave" and editing:
            editor.command("exitTable",{"position":current["position"],"documentId":current["documentId"]})
        elif answer=="delete" and editing:
            editor.command("deleteTable",{"position":current["position"],"documentId":current["documentId"]})
        elif answer=="insert":
            if editing:args.update({"position":current["position"],"documentId":current["documentId"]})
            editor.command("updateTable" if editing else "table",args)
        else:editor.focus_document()
    dialog.connect("response",response);dialog.present()


def textbox_dialog(editor):
    if getattr(editor,"textbox_window",None):editor.textbox_window.present();return
    current=editor.state.get("textbox")
    editing=bool(current)
    dialog=Adw.MessageDialog(transient_for=editor,heading="Text box properties" if editing else "Insert text box")
    editor.textbox_window=dialog
    grid=Gtk.Grid(row_spacing=14,column_spacing=24)
    controls={}
    for row,(key,label,minimum,maximum,default) in enumerate((
            ("width","Width (px):",60,1600,150),("height","Height (px):",40,2000,100),
            ("borderWidth","Border width:",0,12,1))):
        control=Gtk.SpinButton.new_with_range(minimum,maximum,1);control.set_value(default);control.set_width_chars(3)
        control.update_property([Gtk.AccessibleProperty.LABEL],[label.rstrip(":")])
        grid.attach(Gtk.Label(label=label,xalign=0,hexpand=True),0,row,1,1);grid.attach(control,1,row,1,1)
        controls[key]=control
    floating=Gtk.CheckButton(label="Free-floating (text wraps around)",active=True)
    floating.set_tooltip_text("Float the text box to the left; following text flows beside it")
    controls["floating"]=floating;grid.attach(floating,0,3,2,1)
    selected_background=[current.get("background") if editing else None]
    default_colour=Gdk.RGBA()
    default_colour.parse("#2b2d33" if editor.appearance["theme"]=="dark" else "#f8f8f8")
    initial=Gdk.RGBA();initial.parse(selected_background[0] or default_colour.to_string())
    chooser=Gtk.ColorDialog(title="Text box background",with_alpha=True)
    colour=Gtk.ColorDialogButton(dialog=chooser,rgba=initial,tooltip_text="Choose background colour")
    colour.update_property([Gtk.AccessibleProperty.LABEL],["Text box background colour"])
    reset=Gtk.Button(icon_name="edit-clear-symbolic",tooltip_text="Use default background")
    colour_row=Gtk.Box(spacing=4);colour_row.append(colour);colour_row.append(reset)
    grid.attach(Gtk.Label(label="Background:",xalign=0),0,4,1,1);grid.attach(colour_row,1,4,1,1)
    def background_changed(*_):selected_background[0]=colour.get_rgba().to_string()
    colour.connect("notify::rgba",background_changed)
    def default_background(*_):
        colour.set_rgba(default_colour)
        selected_background[0]=None
    reset.connect("clicked",default_background)
    if editing:
        for key in ("width","height","borderWidth"):
            if current[key] is not None:controls[key].set_value(current[key])
        floating.set_active(current["floating"])
    editor.textbox_colour=colour;editor.textbox_reset=reset
    editor.textbox_controls=controls
    dialog.set_extra_child(grid);dialog.add_response("cancel","Cancel");dialog.add_response("insert","Apply" if editing else "Insert")
    dialog.set_response_appearance("insert",Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("insert");dialog.set_close_response("cancel")
    def response(_,answer):
        args={key:control.get_value_as_int() for key,control in controls.items() if key!="floating"}
        args["floating"]=floating.get_active();args["background"]=selected_background[0]
        editor.textbox_window=None;dialog.destroy()
        if answer=="insert":
            if editing:args.update({"position":current["position"],"documentId":current["documentId"]})
            editor.command("updateTextbox" if editing else "textbox",args)
        else:editor.focus_document()
    dialog.connect("response",response);dialog.present()


def image_size_dialog(editor,current):
    if getattr(editor,"image_size_window",None):editor.image_size_window.present();return
    dialog=Adw.MessageDialog(transient_for=editor,heading="Picture size",body="Proportions are preserved. Large pictures fit within the writing area.")
    compact_dialog(dialog);editor.image_size_window=dialog
    natural_width=current.get("naturalWidth") or current.get("displayedWidth") or 300
    natural_height=current.get("naturalHeight") or natural_width
    ratio=natural_height/natural_width
    grid=Gtk.Grid(row_spacing=8,column_spacing=12)
    width=Gtk.SpinButton.new_with_range(1,1600,1);width.set_value(min(1600,current.get("width") or current.get("displayedWidth") or natural_width))
    height=Gtk.SpinButton.new_with_range(1,max(1600,1600*ratio),1);height.set_value(max(1,width.get_value()*ratio))
    updating=False
    def resize(control,from_width):
        nonlocal updating
        if updating:return
        updating=True
        if from_width:height.set_value(max(1,width.get_value()*ratio))
        else:
            width.set_value(max(1,height.get_value()/ratio));height.set_value(max(1,width.get_value()*ratio))
        updating=False
    width.connect("value-changed",lambda control:resize(control,True))
    height.connect("value-changed",lambda control:resize(control,False))
    for row,label,control in ((0,"Width (px):",width),(1,"Height (px):",height)):
        control.set_width_chars(4);control.update_property([Gtk.AccessibleProperty.LABEL],[label.rstrip(":")])
        grid.attach(Gtk.Label(label=label,xalign=0,hexpand=True),0,row,1,1);grid.attach(control,1,row,1,1)
    editor.image_size_controls={"width":width,"height":height}
    dialog.set_extra_child(grid)
    for name,label in (("cancel","Cancel"),("original","Original size"),("apply","Apply")):dialog.add_response(name,label)
    dialog.set_response_appearance("apply",Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("apply");dialog.set_close_response("cancel")
    def response(_,answer):
        editor.image_size_window=None;dialog.destroy()
        if answer in ("apply","original"):
            editor.command("resizeImage",{"position":current["position"],"documentId":current["documentId"],"width":width.get_value_as_int() if answer=="apply" else None})
        else:editor.focus_document()
    dialog.connect("response",response);dialog.present()
