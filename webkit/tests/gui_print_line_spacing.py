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
    folder=ROOT/'.runtime/printed-spacing';folder.mkdir(parents=True,exist_ok=True)
    import xml.etree.ElementTree as ET,json
    measurements={}
    for spacing in (.95,1,1.15,1.5,2,2.5,3):
        html='<p style="line-height:'+str(spacing)+'">FirstLine<br>SecondLine<br>ThirdLine</p>'
        js('window.editor.loadHTML('+json.dumps(html)+')')
        assert js('window.editor.getState()')['json']['content'][0]['attrs']['lineSpacing']==spacing
        output=folder/(str(spacing)+'.pdf')
        if output.exists():output.unlink()
        operation=window.create_print_operation();settings=Gtk.PrintSettings()
        settings.set_printer('Print to File');settings.set('output-uri',output.as_uri());settings.set('output-file-format','pdf')
        operation.set_print_settings(settings)
        done=[];failed=[];operation.connect('finished',lambda _:done.append(True));operation.connect('failed',lambda _,error:failed.append(error.message))
        operation.print_();pump(lambda:bool(done or failed));assert not failed,failed
        result=subprocess.run(['pdftotext','-bbox',str(output),'-'],capture_output=True,text=True,check=True)
        root=ET.fromstring(result.stdout)
        assert sum(1 for e in root.iter() if e.tag.endswith('page'))==1,'Unexpected empty print page'
        words={e.text:float(e.attrib['yMin']) for e in root.iter() if e.tag.endswith('word')}
        gaps=[words['SecondLine']-words['FirstLine'],words['ThirdLine']-words['SecondLine']]
        measurements[spacing]=gaps
        print(f'MEASURED: printed {spacing:g} spacing = {gaps[0]:.3f} pt between lines',flush=True)
    baseline=measurements[1][0]
    for spacing,gaps in measurements.items():
        # WebKit snaps fractional line boxes to print CSS pixels.
        assert all(abs(gap-baseline*spacing)<baseline/16*.51 for gap in gaps),(spacing,gaps,baseline)
    print('PASS: every printed spacing ratio, including 0.95, matches the chosen document spacing',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
