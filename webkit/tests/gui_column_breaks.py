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
    import json,xml.etree.ElementTree as ET
    for count in (2,3):
        html=''.join('<p>ColumnMark'+str(i)+' '+('Words flow across this column. '*10)+'</p>' for i in range(6))+'<hr data-page-break="true"><p>AfterBreak full width</p>'
        js('window.editor.loadHTML('+json.dumps(html)+')')
        js('window.editor.exec("columns",{value:'+str(count)+'})');pump(minimum=.3)
        geometry=js("""(()=>{const root=window.editor.view.dom;const br=root.querySelector('[data-page-break]');const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,bottom:r.bottom}};return {before:rect(br.previousElementSibling),line:rect(br),after:rect(br.nextElementSibling),first:rect(root.querySelector('p'))}})()""")
        assert geometry['after']['y']>geometry['line']['bottom'],geometry
        assert abs(geometry['after']['x']-geometry['first']['x'])<2,geometry
        assert geometry['after']['width']>geometry['first']['width']*1.8,geometry
        assert geometry['before']['bottom']<=geometry['line']['y']+1,geometry
        output=ROOT/'.runtime'/('columns-'+str(count)+'.pdf')
        if output.exists():output.unlink()
        operation=window.create_print_operation();settings=Gtk.PrintSettings()
        settings.set_printer('Print to File');settings.set('output-uri',output.as_uri());settings.set('output-file-format','pdf')
        operation.set_print_settings(settings)
        done=[];failed=[]
        operation.connect('finished',lambda _:done.append(True));operation.connect('failed',lambda _,error:failed.append(error.message))
        operation.print_();pump(lambda:bool(done or failed));assert not failed,failed
        result=subprocess.run(['pdftotext','-bbox',str(output),'-'],capture_output=True,text=True,check=True)
        pdf=ET.fromstring(result.stdout);pages=[e for e in pdf.iter() if e.tag.endswith('page')]
        assert len(pages)==2,[(e.attrib) for e in pages]
        words=[e for e in pages[0].iter() if e.tag.endswith('word')]
        markers=[float(e.attrib['xMin']) for e in words if (e.text or '').startswith('ColumnMark')]
        assert len(markers)==6,markers
        assert max(markers)-min(markers)>100,('Printed columns collapsed',count,markers)
        assert any(e.text=='AfterBreak' for e in pages[1].iter()),'Missing text after break'
        print('PASS:',count,'columns visible on screen and PDF; after break full width; marker positions',markers,flush=True)
        before=js('window.editor.getState()')
        window.show_print_preview();pump(lambda:window.print_dialog is not None)
        preview=window.print_preview
        if not preview.busy:preview.generate()
        pump(lambda:preview.pages==2 and not preview.busy)
        preview_text=subprocess.run(['pdftotext','-bbox',str(preview.pdf),'-'],capture_output=True,text=True,check=True).stdout
        preview_xml=ET.fromstring(preview_text)
        preview_markers=[float(e.attrib['xMin']) for e in preview_xml.iter() if e.tag.endswith('word') and (e.text or '').startswith('ColumnMark')]
        assert len(preview_markers)==6 and max(preview_markers)-min(preview_markers)>100,preview_markers
        assert preview.picture.get_paintable() is not None
        if count==3:
            pump(minimum=.3)
            subprocess.run(['import','-window','root',str(ROOT/'.runtime/column-preview.png')],check=True)
        window.print_dialog.response(Gtk.ResponseType.CANCEL);pump()
        assert js('window.editor.getState()')==before,'Printing changed document content'
        print('PASS:',count,'columns also preserved in native print preview',flush=True)

    # A single formatted paragraph must split between cells without losing text.
    import re
    source=' '.join('word'+str(i) for i in range(300))
    js('window.editor.loadHTML('+json.dumps('<p><strong>'+source[:len(source)//2]+'</strong>'+source[len(source)//2:]+'</p>')+')')
    js('window.editor.exec("columns",{value:3})');pump(minimum=.2)
    output=ROOT/'.runtime/columns-formatted.pdf'
    if output.exists():output.unlink()
    operation=window.create_print_operation();settings=Gtk.PrintSettings()
    settings.set_printer('Print to File');settings.set('output-uri',output.as_uri());settings.set('output-file-format','pdf')
    operation.set_print_settings(settings);done=[];failed=[]
    operation.connect('finished',lambda _:done.append(True));operation.connect('failed',lambda _,error:failed.append(error.message))
    operation.print_();pump(lambda:bool(done or failed));assert not failed,failed
    text=subprocess.run(['pdftotext','-raw',str(output),'-'],capture_output=True,text=True,check=True).stdout
    assert re.sub(r'\s','',text)==re.sub(r'\s','',source),'Text lost or reordered across print columns'
    print('PASS: formatted paragraph splits across print columns without text loss',flush=True)
finally:
    window.discard_confirmed=True;window.close();prefs.cleanup()
