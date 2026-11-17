import http from 'node:http';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
const base=fileURLToPath(new URL('.',import.meta.url));
const evidence=[];
const model='context-e2e-mock';
function log(row){evidence.push({time:new Date().toISOString(),...row});fs.writeFileSync(base+'/model-evidence.json',JSON.stringify(evidence,null,2));}
function textOf(message){return typeof message?.content==='string'?message.content:(message?.content||[]).map(p=>p.text||'').join('\n');}
function responseFor(body){
 const messages=body.messages||[];
 const latest=textOf(messages.at(-1));
 const system=messages.filter(m=>m.role==='system'||m.role==='developer').map(textOf).join('\n');
 if(!system.includes('Thought, Action, PAUSE, Observation')) {log({kind:'auxiliary',messageCount:messages.length});return 'Context web retrieval verification';}
 if(!latest.startsWith('Observation:')) {log({kind:'search-action',model:body.model});return 'Thought: I must retrieve current official source evidence.\nAction: google: Context.dev official web scraping search API\nPAUSE';}
 const raw=latest.slice('Observation:'.length).trim();
 let data;try{data=JSON.parse(raw);}catch{}
 const pages=data?.pages||data?.results||[];
 const official=pages.find(p=>(p.link||p.url||'').includes('context.dev'));
 const source=official&&(official.link||official.url);
 if(!official||!source||/error occurred|Missing Google/i.test(raw)) {log({kind:'rejected-observation',observationCharacters:raw.length,sourceUrls:pages.map(p=>p.link||p.url).filter(Boolean)});return 'Answer: E2E_FAILED: live Context source evidence was missing.';}
 const snippet=official.snippet||official.description||official.text||official.title||'';
 log({kind:'grounded-answer',source,sourceCount:pages.length,observationCharacters:raw.length,excerpt:snippet.slice(0,600)});
 return `Answer: Live retrieval verified. ${snippet.slice(0,450)} Source: [${official.title||'Context.dev'}](${source}).`;
}
const server=http.createServer(async(req,res)=>{
 res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Headers','content-type,authorization');res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');
 if(req.method==='OPTIONS'){res.writeHead(204);return res.end();}
 if(req.url==='/__evidence'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(evidence));}
 if(req.url==='/__reset'&&req.method==='POST'){evidence.length=0;fs.writeFileSync(base+'/model-evidence.json','[]');return res.end('{}');}
 if(req.method==='GET'&&req.url.includes('/models')){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify({object:'list',data:[{id:model,object:'model',created:1700000000,owned_by:'local-e2e'}]}));}
 if(req.method==='POST'&&req.url.includes('/chat/completions')){
  let raw='';for await(const chunk of req)raw+=chunk;
  const body=JSON.parse(raw);const content=responseFor(body);const id='chatcmpl-e2e-'+Date.now();const created=Math.floor(Date.now()/1000);
  if(body.stream){res.writeHead(200,{'Content-Type':'text/event-stream'});res.write('data: '+JSON.stringify({id,object:'chat.completion.chunk',created,model,choices:[{index:0,delta:{role:'assistant',content},finish_reason:null}]})+'\n\n');res.write('data: '+JSON.stringify({id,object:'chat.completion.chunk',created,model,choices:[{index:0,delta:{},finish_reason:'stop'}],usage:{prompt_tokens:100,completion_tokens:50,total_tokens:150}})+'\n\n');res.end('data: [DONE]\n\n');}
  else{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({id,object:'chat.completion',created,model,choices:[{index:0,message:{role:'assistant',content},finish_reason:'stop'}],usage:{prompt_tokens:100,completion_tokens:50,total_tokens:150}}));}
  return;
 }
 res.writeHead(404,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{message:'Unsupported mock route',path:req.url}}));
});server.listen(3438,'127.0.0.1',()=>console.log('Deterministic E2E LLM listening on http://127.0.0.1:3438'));
