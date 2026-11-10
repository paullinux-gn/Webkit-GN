"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
from app import App,GLib,Gtk
app=App();app.register(None);app.activate();window=app.get_active_window();context=GLib.MainContext.default()
errors=[]
sys.excepthook=lambda kind,error,tb:(errors.append(str(error)),sys.__excepthook__(kind,error,tb))
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
    from toolbar import style_dialog
    folder=ROOT/'.runtime/font-search';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p>Font search keeps this selection.</p>")');js('window.editor.select(1,12)')
    def descendants(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from descendants(child);child=child.get_next_sibling()
    def test_search(dropdown):
        assert dropdown.get_expression() is not None
        button=next(w for w in descendants(dropdown) if isinstance(w,Gtk.Button))
        button.emit('clicked');pump()
        search=next(w for w in descendants(dropdown) if isinstance(w,Gtk.SearchEntry))
        view=next(w for w in descendants(dropdown) if isinstance(w,Gtk.ListView))
        model=view.get_model();all_count=model.get_n_items();assert all_count==len(window.font_names)
        search.set_text('MONO');pump(lambda:model.get_n_items()<all_count,minimum=.3)
        matches=[model.get_item(i).get_string() for i in range(model.get_n_items())]
        assert matches and all('mono' in name.casefold() for name in matches),matches
        search.set_text('not-a-real-font-name');pump(lambda:model.get_n_items()==0,minimum=.3)
        search.set_text('');pump(lambda:model.get_n_items()==all_count,minimum=.3)
        search.set_text('mono');pump(lambda:0<model.get_n_items()<all_count,minimum=.3)
        subprocess.run(['import','-window','root',str(folder/'filtered.png')],check=True)
        selected=model.get_item(0).get_string();view.emit('activate',0);pump()
        return selected
    selected=test_search(window.fonts);pump(lambda:window.state['format']['font']==selected)
    assert js('window.editor.getText()')=='Font search keeps this selection.'
    selection=js('({from:window.editor.view.state.selection.from,to:window.editor.view.state.selection.to})')
    assert selection=={'from':1,'to':12},selection
    before=js('window.editor.getState()')['json']
    style_dialog(window,False);pump()
    dropdown=next(w for w in descendants(window.style_dialog.get_extra_child()) if isinstance(w,Gtk.DropDown) and w.get_enable_search())
    test_search(dropdown);window.style_dialog.response('cancel');pump()
    assert js('window.editor.getState()')['json']==before
    print('PASS: toolbar and style font searches filter by case-insensitive substring; no-match/clear/search selection work and document selection is preserved',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
