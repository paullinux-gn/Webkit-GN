"""Two-row toolbar, rule insertion and native print/PDF regression checks."""
from pathlib import Path
import os,sys,time,tempfile,subprocess
import ctypes as C
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"webkit"))
preferences=tempfile.TemporaryDirectory(prefix="gnome-wp-layout-")
os.environ["GNOME_WP_SETTINGS_FILE"]=str(Path(preferences.name)/"settings.json")
from app import App,GLib,Gtk
from toolbar import THEMED_ICONS

errors=[];previous=sys.excepthook
def record(kind,error,tb):errors.append(str(error));previous(kind,error,tb)
sys.excepthook=record
app=App();app.register(None);app.activate();window=app.get_active_window();context=GLib.MainContext.default()
folder=ROOT/".runtime/layout-print";folder.mkdir(parents=True,exist_ok=True)
def pump(predicate=lambda:True,minimum=.1):
    start=time.monotonic()
    while time.monotonic()-start<minimum or not predicate():
        if time.monotonic()-start>25:raise AssertionError("Layout/print test timed out: "+window.status.get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.002)
    assert not errors,errors
def js(expression):
    result=[];failures=[];window.js(expression,result.append,failures.append);pump(lambda:bool(result or failures))
    assert not failures,failures
    return result[0]
def children(widget):
    yield widget;child=widget.get_first_child()
    while child:yield from children(child);child=child.get_next_sibling()
try:
    pump(lambda:window.state.get("ready"))
    assert len(window.toolbar_rows)==2
    rows=[];child=window.tools.get_first_child()
    while child:rows.append(child);child=child.get_next_sibling()
    assert len(rows)==3 and isinstance(rows[1],Gtk.Separator)
    assert rows[1].has_css_class("toolbar-row-divider") and rows[1].get_height()==1
    assert all(isinstance(rows[i],Gtk.ScrolledWindow) for i in (0,2))
    for row in window.toolbar_rows:
        dividers=[w for w in children(row) if w.has_css_class("toolbar-divider")]
        assert dividers and all(w.get_width()==1 for w in dividers)
    theme=Gtk.IconTheme.get_for_display(window.get_display())
    assert all(theme.has_icon(name) for name in THEMED_ICONS.values())
    labels=[widget for widget in children(window.toolbar_rows[0]) if isinstance(widget,Gtk.Label)]
    assert labels and all(int(label.get_pango_context().get_font_description().get_weight())==400 for label in labels)
    assert window.alignment_image.get_gicon().get_names()[0]=="format-justify-fill-symbolic"
    window.alignment_buttons["right"].emit("clicked");pump(lambda:window.state["format"]["align"]=="right")
    assert window.alignment_image.get_gicon().get_names()[0]=="format-justify-fill-symbolic"
    print("PASS: two persistent rows, normal-weight labels, fixed visible justify icon",flush=True)
    # Real pointer hover/click: selected document formatting must keep the accent
    # after leaving the button, and follow the cursor back into unformatted text.
    js('window.editor.loadHTML("<p>Select this text for formatting.</p>")')
    js("window.editor.select(1,7)")
    button=window.toggle_buttons["bold"]
    original=button.get_color().to_string()
    x11=C.CDLL("libX11.so.6");xtest=C.CDLL("libXtst.so.6")
    x11.XOpenDisplay.argtypes=[C.c_char_p];x11.XOpenDisplay.restype=C.c_void_p
    x11.XFlush.argtypes=[C.c_void_p];x11.XCloseDisplay.argtypes=[C.c_void_p]
    xtest.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
    display=x11.XOpenDisplay(None);assert display
    def move(x,y):
        xtest.XTestFakeMotionEvent(display,-1,round(x),round(y),0);x11.XFlush(display);pump(minimum=.2)
    ok,bounds=button.compute_bounds(window);assert ok
    move(bounds.get_x()+bounds.get_width()/2,bounds.get_y()+bounds.get_height()/2)
    assert button.get_state_flags() & Gtk.StateFlags.PRELIGHT
    subprocess.run(["import","-window","root",str(folder/"toolbar-hover.png")],check=True)
    xtest.XTestFakeButtonEvent(display,1,True,0);xtest.XTestFakeButtonEvent(display,1,False,0);x11.XFlush(display)
    pump(lambda:window.state["format"]["strong"])
    assert button.get_active() and button.get_color().to_string()!=original
    move(1050,700)
    assert not button.get_state_flags() & Gtk.StateFlags.PRELIGHT
    assert button.get_active()
    subprocess.run(["import","-window","root",str(folder/"toolbar-selected.png")],check=True)
    js("window.editor.select(12)");pump(lambda:not button.get_active())
    assert button.get_color().to_string()==original
    x11.XCloseDisplay(display)
    print("PASS: Twinly themed icons, fine row/group dividers, real pointer hover and selection-following accent state",flush=True)
    js('window.editor.loadHTML("<p>Toolbar print verification.</p><p></p>")')
    js("window.editor.select(window.editor.view.state.doc.content.size-1)")
    window.action_buttons["horizontalRule"].emit("clicked");pump()
    geometry=js('({line:document.querySelector(".ProseMirror hr").getBoundingClientRect().width,paper:document.getElementById("editor").getBoundingClientRect().width})')
    assert geometry["line"]>.8*geometry["paper"],geometry
    js('window.editor.exec("insertText",{text:"Text after the horizontal line."})')
    assert js("window.editor.getText()").endswith("Text after the horizontal line.")

    dismissed=[]
    def dismiss_print():
        for dialog in Gtk.Window.get_toplevels():
            if dialog!=window and "print" in type(dialog).__name__.lower():
                dialog.response(Gtk.ResponseType.CANCEL);dismissed.append(True);return False
        return True
    timeout=GLib.timeout_add(100,dismiss_print)
    window.print_button.emit("clicked")
    pump(lambda:bool(dismissed))
    print("PASS: printer icon opens the native print dialog",flush=True)

    output=folder/"print-test.pdf"
    if output.exists():output.unlink()
    operation=window.create_print_operation();settings=Gtk.PrintSettings()
    settings.set_printer("Print to File");settings.set("output-uri",output.as_uri());settings.set("output-file-format","pdf")
    operation.set_print_settings(settings)
    done=[];failed=[]
    operation.connect("finished",lambda _:done.append(True))
    operation.connect("failed",lambda _,error:failed.append(error.message))
    operation.print_();pump(lambda:bool(done or failed))
    assert not failed,failed
    assert output.read_bytes().startswith(b"%PDF-") and output.stat().st_size>500
    print("PASS: full-width rule, continued typing and actual A4 PDF print output",flush=True)
    pump(minimum=.2)
    subprocess.run(["import","-window","root",str(folder/"toolbar.png")],check=True)
finally:
    window.discard_confirmed=True;window.close();preferences.cleanup()
