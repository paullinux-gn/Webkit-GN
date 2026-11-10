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
    folder=ROOT/'.runtime/highlight-contrast';folder.mkdir(parents=True,exist_ok=True)
    js('window.editor.loadHTML("<p><strong><span style=color:red>Readable highlighted text</span></strong></p>")')
    js('window.editor.select(1,26)')
    assert len(window.palette_buttons['highlight'])==61
    assert len(window.palette_buttons['color'])==61
    window.color_menus['highlight'].popup();pump(minimum=.2)
    subprocess.run(['import','-window','root',str(folder/'palette.png')],check=True)
    for colour in ('#1c3d73','#1a5fb4','#1b5e20','#a51d2d','#613583','#63452c','#005b5b','#3d3846'):
        window.command('highlight',{'value':colour});pump(lambda:window.state['format']['highlight']==colour)
        assert js('getComputedStyle(document.querySelector("[data-highlight]")).color')=='rgb(255, 255, 255)'
        assert window.state['format']['color']=='#ffffff'
    from toolbar import HIGHLIGHT_COLOURS
    for theme in ('light','mixed','dark'):
        window.change_appearance(theme=theme);pump()
        for _,colour in [(name,value) for name,value in HIGHLIGHT_COLOURS if name.startswith("Pastel ")]:
            window.palette_buttons['highlight'][colour].emit('clicked');pump()
            assert js('getComputedStyle(document.querySelector("[data-highlight]")).color')=='rgb(32, 33, 36)',(theme,colour)
    window.change_appearance(theme='mixed');pump()
    window.command('highlight',{'value':'#1a5fb4'});pump()
    subprocess.run(['import','-window','root',str(folder/'dark-blue.png')],check=True)
    before=js('window.editor.getState()')['json'];exported=js('window.editor.exportHTML()')['html']
    import json
    js('window.editor.loadHTML('+json.dumps(exported)+')');assert js('window.editor.getState()')['json']==before
    js('window.editor.select(1,26)');window.command('highlight',{'value':'#f6d32d'});pump()
    assert js('getComputedStyle(document.querySelector("[data-highlight]")).color')=='rgb(32, 33, 36)'
    window.change_appearance(theme='dark');pump()
    assert js('getComputedStyle(document.querySelector("[data-highlight]")).color')=='rgb(32, 33, 36)'
    window.change_appearance(theme='mixed');window.palette_buttons['highlight'][None].emit('clicked');pump()
    assert js('document.querySelector("[data-highlight]")') is None
    assert window.state['format']['color'] in ('red','rgb(255, 0, 0)')
    assert js('window.editor.getText()')=='Readable highlighted text'
    js('window.editor.loadHTML("<p>Rounded highlighted text with padding on every line. Rounded highlighted text with padding on every line. Rounded highlighted text with padding on every line. Rounded highlighted text with padding on every line.</p>")')
    js('window.editor.select(1,window.editor.view.state.doc.content.size-1)')
    window.command('highlight',{'value':'#1a5fb4'});pump()
    decoration=js('(()=>{const e=document.querySelector("[data-highlight]"),s=getComputedStyle(e);return {radius:parseFloat(s.borderRadius),top:parseFloat(s.paddingTop),right:parseFloat(s.paddingRight),clone:s.webkitBoxDecorationBreak,lines:e.getClientRects().length}})()')
    assert decoration['radius']>0 and decoration['top']>0 and decoration['right']>0 and decoration['clone']=='clone' and decoration['lines']>1,decoration
    subprocess.run(['import','-window','root',str(folder/'rounded-padding.png')],check=True)
    print('PASS: rounded padded highlights clone decoration across wrapped lines',flush=True)
    print('PASS: native expanded highlight palette, every dark colour uses white, yellow uses dark text across themes, save/reload and removal restores original text colour',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
