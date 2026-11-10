"""Native dropdown, custom-style and colour-palette regression checks."""
from pathlib import Path
import os,sys,time,tempfile,subprocess,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"webkit"))
preferences=tempfile.TemporaryDirectory(prefix="gnome-wp-toolbar-")
os.environ["GNOME_WP_SETTINGS_FILE"]=str(Path(preferences.name)/"settings.json")
from app import App,GLib,Gtk
from toolbar import style_dialog

errors=[];old_hook=sys.excepthook
def record(kind,error,tb):errors.append(str(error));old_hook(kind,error,tb)
sys.excepthook=record
app=App();app.register(None);app.activate();window=app.get_active_window();context=GLib.MainContext.default()
folder=ROOT/".runtime/toolbar";folder.mkdir(parents=True,exist_ok=True)
def pump(predicate=lambda:True,minimum=.1):
    start=time.monotonic()
    while time.monotonic()-start<minimum or not predicate():
        if time.monotonic()-start>20:raise AssertionError("Toolbar test timed out: "+window.status.get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)
    assert not errors,errors
def js(expression):
    values=[];failures=[];window.js(expression,values.append,failures.append);pump(lambda:bool(values or failures))
    assert not failures,failures
    return values[0]
def capture(name):
    pump(minimum=.2);subprocess.run(["import","-window","root",str(folder/(name+".png"))],check=True)
def children(widget):
    yield widget;child=widget.get_first_child()
    while child:yield from children(child);child=child.get_next_sibling()
try:
    pump(lambda:window.state.get("ready"))
    js('window.editor.loadHTML("<p>Selected text keeps its formatting.</p><p>Second paragraph.</p>")')
    js("window.editor.select(1,14)")
    window.styles.popup();capture("styles")
    window.style_buttons["H2"].emit("clicked");pump(lambda:window.state["format"]["style"]=="H2")
    window.fonts.set_selected(window.font_names.index("Serif"));pump(lambda:window.state["format"]["font"]=="Serif")
    window.size.set_selected(window.size_values.index("18"));pump(lambda:window.state["format"]["size"]=="18pt")
    style_dialog(window,True);pump()
    dialog=window.style_dialog
    name=next(w for w in children(dialog.get_extra_child()) if isinstance(w,Gtk.Entry))
    name.set_text("Chapter custom");dialog.response("save")
    pump(lambda:window.state["format"]["style"]=="Chapter custom")
    assert window.state["styles"]["Chapter custom"]["font"]=="Serif"
    assert window.state["styles"]["Chapter custom"]["level"]==2
    style_dialog(window,False);pump();dialog=window.style_dialog
    size=next(w for w in children(dialog.get_extra_child()) if isinstance(w,Gtk.SpinButton));size.set_value(20)
    bold=next(w for w in children(dialog.get_extra_child()) if isinstance(w,Gtk.CheckButton) and w.get_label()=="Bold");bold.set_active(False)
    dialog.response("save");pump(lambda:window.state["styles"]["Chapter custom"]["size"]==20)
    assert window.state["format"]["size"]=="20pt"
    assert not window.state["format"]["strong"]
    print("PASS: native style/font/size dropdowns; create/edit reusable heading style",flush=True)

    window.alignment_menu.popup();capture("alignment")
    window.alignment_buttons["center"].emit("clicked");pump(lambda:window.state["format"]["align"]=="center")
    assert js("window.editor.getState()")["json"]["content"][0]["attrs"]["align"]=="center"
    window.alignment_menu.popup();window.alignment_buttons["left"].emit("clicked");pump(lambda:window.state["format"]["align"]=="left")

    window.toggle_buttons["bold"].emit("clicked");pump(lambda:window.state["format"]["strong"])
    window.color_menus["color"].popup();capture("text-colours")
    window.command("color",{"value":"#e01b24"});pump(lambda:window.state["format"]["color"]=="#e01b24")
    window.color_menus["highlight"].popup();capture("highlight-colours")
    window.command("highlight",{"value":"#f6d32d"});pump(lambda:window.state["format"]["highlight"]=="#f6d32d")
    window.color_menus["color"].popup();window.palette_buttons["color"][None].emit("clicked");pump(lambda:window.state["format"]["color"]=="#202124")
    assert not js('window.editor.view.state.doc.firstChild.firstChild.marks.some(mark=>mark.type.name==="color")')
    assert window.state["format"]["highlight"]=="#f6d32d" and window.state["format"]["strong"]
    window.color_menus["highlight"].popup();window.palette_buttons["highlight"][None].emit("clicked");pump(lambda:window.state["format"]["highlight"] is None)
    assert window.state["format"]["strong"]
    exported=js("window.editor.exportHTML()")["html"]
    js("window.editor.loadHTML("+json.dumps(exported)+")")
    assert js("window.editor.getState()")["json"]["attrs"]["styles"]["Chapter custom"]["size"]==20
    assert not js("window.editor.getSummary()")["dirty"]
    capture("grouped-toolbar")
    print("PASS: alignment dropdown and both swatch palettes preserve selection; remove-colour keeps bold and other colour; styles survive HTML reload",flush=True)
finally:
    window.discard_confirmed=True;window.close();preferences.cleanup()
