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
    import json
    js('window.editor.loadHTML("<p>First styled paragraph</p><p>Second styled paragraph</p>")')
    js('window.editor.select(1)')
    for index,(kind,size) in enumerate((('Body',12),('Title',30),('H1',24),('H2',18),('H3',14))):
        style_dialog(window,True);pump();controls=window.style_controls
        model=controls['kind'].get_model()
        assert [model.get_string(i) for i in range(model.get_n_items())]==['Body','Title','H1','H2','H3']
        controls['kind'].set_selected(index);pump()
        assert controls['size'].get_value()==size,(kind,controls['size'].get_value())
        controls['name'].set_text('My '+kind);window.style_dialog.response('save')
        pump(lambda:window.state['format']['style']=='My '+kind)
        assert window.state['styles']['My '+kind]['kind']==kind
    window.styles.popup();pump()
    assert window.style_popover.has_css_class('compact-menu')
    assert all(button.get_height()<=30 for button in window.style_buttons.values())
    window.styles.popdown()
    window.command('style',{'name':'My Title'});pump(lambda:window.state['format']['style']=='My Title')
    js('window.editor.select(window.editor.view.state.doc.firstChild.nodeSize+1)')
    window.command('style',{'name':'My Title'});pump(lambda:window.state['format']['style']=='My Title')
    style_dialog(window,False);pump();controls=window.style_controls
    assert controls['name'].get_editable()
    assert window.style_dialog.has_css_class('compact-editor-dialog')
    def descendants(widget):
        yield widget;child=widget.get_first_child()
        while child:yield from descendants(child);child=child.get_next_sibling()
    action_buttons=[w for w in descendants(window.style_dialog) if isinstance(w,Gtk.Button) and w.get_label() in ('Cancel','Apply')]
    assert len(action_buttons)==2 and all(w.get_height()<=34 and w.get_width()<110 for w in action_buttons)
    controls['name'].set_text('H1');pump();assert not window.style_dialog.get_response_enabled('save')
    controls['name'].set_text('Document title');controls['size'].set_value(32)
    assert window.style_dialog.get_response_enabled('save')
    folder=ROOT/'.runtime/custom-styles';folder.mkdir(parents=True,exist_ok=True)
    pump(minimum=.2);subprocess.run(['import','-window','root',str(folder/'rename.png')],check=True)
    window.style_dialog.response('save');pump(lambda:window.state['format']['style']=='Document title')
    doc=js('window.editor.getState()')['json']
    assert 'My Title' not in doc['attrs']['styles']
    assert all(block['attrs']['styleName']=='Document title' for block in doc['content'])
    assert doc['attrs']['styles']['Document title']['size']==32
    assert doc['attrs']['styles']['Document title']['kind']=='Title'
    assert 'Document title' in window.style_buttons and 'My Title' not in window.style_buttons
    window.command('undo');pump(lambda:window.state['format']['style']=='My Title')
    window.command('redo');pump(lambda:window.state['format']['style']=='Document title')
    exported=js('window.editor.exportHTML()')['html'];js('window.editor.loadHTML('+json.dumps(exported)+')')
    assert js('window.editor.getState()')['json']==doc
    print('PASS: native custom styles for Body/Title/H1/H2/H3, correct defaults, editable names, collision blocking, document-wide rename, menu refresh, undo and HTML reopen',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
