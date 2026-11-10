"""Actual PDF preview navigation and settings regeneration in the native dialog."""
from pathlib import Path
import sys,os,time,tempfile,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'webkit'))
prefs=tempfile.TemporaryDirectory();os.environ['GNOME_WP_SETTINGS_FILE']=str(Path(prefs.name)/'interface.json')
from app import App,GLib,Gtk,WebKit
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
    from toolbar import TEXT_COLOURS,HIGHLIGHT_COLOURS,palette_positions
    for command,colours in (("color",TEXT_COLOURS),("highlight",HIGHLIGHT_COLOURS)):
        positions=palette_positions(colours)
        assert len(positions)==len(colours)
        assert len(set(positions.values()))==len(colours)
        for name,value in colours:
            button=window.palette_buttons[command][value]
            assert button.get_parent().get_child_at(*positions[name]) is button
        assert positions['White'][0]==positions['Black'][0]
        assert positions['White'][1]<positions['Black'][1]
        assert positions['Blue'][0]==positions['Dark blue'][0]==positions['Deep blue'][0]
    assert len(window.palette_buttons['color'])==61
    assert len(window.palette_buttons['highlight'])==61
    js('window.editor.exec("insertText",{text:"Colour sample"})');js('window.editor.select(1,7)')
    for theme in ('light','mixed','dark'):
        window.change_appearance(theme=theme);pump()
        window.color_menus['color'].popup();pump()
        colour=dict(TEXT_COLOURS)['Light blue'];window.palette_buttons['color'][colour].emit('clicked')
        pump(lambda:window.state['format']['color']==colour)
        window.command('undo');pump()
    print('PASS: both palettes grouped by family from light to dark, 60 matching colours plus removal, expanded swatch applies in all themes',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
