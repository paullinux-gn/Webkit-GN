"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
from app import App,GLib,Gtk
app=App();app.register(None);app.activate();window=app.get_active_window();context=GLib.MainContext.default()
errors=[]
sys.excepthook=lambda kind,error,tb:errors.append(str(error))
def pump(predicate=lambda:True,minimum=.1):
    start=time.monotonic()
    while time.monotonic()-start<minimum or not predicate():
        assert time.monotonic()-start<60,(errors,getattr(getattr(window,'print_preview',None),'label',window.status).get_text())
        for _ in range(100):
            if not context.pending():break
            context.iteration(False)
        time.sleep(.003)
    assert not errors,errors

def js(text):
    result=[];window.js(text,result.append);pump(lambda:bool(result));return result[0]
try:
    pump(lambda:window.state.get('ready'))
    js('window.editor.loadHTML("<h1>Print preview test</h1><p>First page.</p><hr data-page-break=\\"true\\"><h1>Second page</h1><p>Second page content.</p>")')
    window.print_button.emit('clicked');pump(lambda:window.print_dialog is not None)
    preview=window.print_preview;preview.generate();pump(lambda:preview.pages>=2 and not preview.busy)
    assert preview.picture.get_paintable() is not None
    assert preview.pdf.read_bytes().startswith(b'%PDF-')
    preview.next.emit('clicked');pump(lambda:preview.page==2 and not preview.busy)
    assert preview.label.get_text().startswith('Page 2 of')
    preview.previous.emit('clicked');pump(lambda:preview.page==1 and not preview.busy)
    page=window.print_dialog.get_page_setup();page.set_orientation(Gtk.PageOrientation.LANDSCAPE)
    window.print_dialog.set_page_setup(page);preview.refresh.emit('clicked');pump(lambda:not preview.busy)
    assert preview.picture.get_paintable().get_intrinsic_width()>preview.picture.get_paintable().get_intrinsic_height()
    # Show the preview tab as a user would, for the review screenshot.
    def visit(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from visit(child);child=child.get_next_sibling()
    selected=False
    for widget in visit(window.print_dialog):
        if isinstance(widget,Gtk.Notebook):
            for index in range(widget.get_n_pages()):
                page=widget.get_nth_page(index)
                if page is preview.box or preview.box.is_ancestor(page):
                    widget.set_current_page(index);selected=True
    assert selected,"Preview tab not found"
    pump(lambda:preview.box.get_mapped(),minimum=.3)
    folder=ROOT/'.runtime/print-preview';folder.mkdir(parents=True,exist_ok=True)
    subprocess.run(['import','-window','root',str(folder/'preview.png')],check=True)
    window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
    assert window.print_dialog is None and not js('window.editor.getSummary()')['dirty']
    # Exercise the dialog's real Print response, rather than just the renderer.
    window.print_document();pump(lambda:window.print_dialog is not None)
    output=folder/'dialog-output.pdf'
    if output.exists():output.unlink()
    settings=Gtk.PrintSettings();settings.set_printer('Print to File')
    settings.set('output-uri',output.as_uri());settings.set('output-file-format','pdf')
    window.print_dialog.set_settings(settings);pump(minimum=.3)
    window.print_dialog.response(Gtk.ResponseType.OK)
    pump(lambda:output.exists() and output.stat().st_size>500)
    assert output.read_bytes().startswith(b'%PDF-')
    print('PASS: native Print response writes the selected PDF output',flush=True)
    print('PASS: native Print window embeds actual PDF preview; page navigation, landscape regeneration, cancellation and clean document',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
