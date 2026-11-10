import {JSDOM} from 'jsdom';
import {pathToFileURL} from 'node:url';
import {performance} from 'node:perf_hooks';
const dom=new JSDOM('<!doctype html><body></body>',{pretendToBeVisual:true,url:'https://editor.invalid'});
globalThis.window=dom.window;globalThis.document=dom.window.document;
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.getComputedStyle=dom.window.getComputedStyle.bind(dom.window);
dom.window.scrollTo=()=>{};
dom.window.Range.prototype.getClientRects=()=>[];
dom.window.Range.prototype.getBoundingClientRect=()=>({left:0,right:0,top:0,bottom:0,width:0,height:0});
const target=process.argv[2]?pathToFileURL(process.argv[2]).href:new URL('../src/editor.js',import.meta.url).href;
const {createEditor}=await import(target);
const mount=document.createElement('div');document.body.append(mount);
const api=createEditor(mount,state=>JSON.stringify(state));
const styles=Object.fromEntries(Array.from({length:100},(_,i)=>['Style '+i,{kind:'Body',level:0,font:'Sans',size:12,bold:false,italic:false}]));
const html='<body data-editor-styles=\''+JSON.stringify(styles)+'\'>'+('<p>'+('the quick brown fox jumps over the lazy dog. '.repeat(10))+'</p>').repeat(800)+'</body>';
const results={paragraphs:800,customStyles:100};
function measure(name,count,fn){for(let i=0;i<5;i++)fn();const start=performance.now();for(let i=0;i<count;i++)fn();results[name]={iterations:count,ms:+(performance.now()-start).toFixed(2)};}
try{
  api.loadHTML(html);api.select(api.view.state.doc.content.size-1);api.exec('insertText',{text:' edited'});
  measure('dirty_status',2000,()=>api.getSummary());
  measure('formatting_notifications',150,()=>api.exec('italic'));
  api.find('the');
  measure('formatting_with_search',150,()=>api.exec('italic'));
  measure('repeat_find',15,()=>api.find('the'));
  console.log(JSON.stringify(results));
}finally{api.destroy();dom.window.close();}
