#!/usr/bin/env python3
"""UI -> ReAct -> live Context -> mock observation -> sourced UI answer.
Run from the Big-AGI checkout with mock-llm.mjs running. Only the LLM is mocked.
Uses a separate named browser. BIGAGI_BASE_URL optionally overrides localhost:3437.
Requires dev server CONTEXT_DEV_API_KEY; never reads or stores that credential.
"""
import datetime,json,os,pathlib,re,subprocess,time,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
SESSION='bigagi-e2e'
URL=os.environ.get('BIGAGI_BASE_URL','http://localhost:3437')

def ab(*args):
    p=subprocess.run(['agent-browser','--session',SESSION,*args],capture_output=True,text=True,check=True)
    return p.stdout

def body(): return ab('get','text','body')
def ref(role,label,index=0):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        snap=ab('snapshot','-i')
        rows=[r for r in snap.splitlines() if re.search(r'\b'+re.escape(role)+r' "'+re.escape(label)+r'"',r)]
        if rows:return '@'+re.search(r'ref=(e\d+)',rows[index]).group(1)
        time.sleep(0.1)
    raise AssertionError('Missing UI control: '+role+' '+label)
def click(role,label,index=0): ab('click',ref(role,label,index))
def open_preferences():
    ab('focus',ref('button','App Preferences'))
    ab('press','Enter')
def fill(role,label,value): ab('fill',ref(role,label),value)
def close_dialog(): click('button','Close Dialog',-1)
def setup_model():
    click('button','Add Language Models - REQUIRED')
    if "I have a key" in body():close_dialog()
    if 'advanced configuration' in body():click('link','advanced configuration')
    click('button','Add your first AI service')
    click('menuitem','OpenAI')
    if 'API Endpoint' not in body():
        snap=ab('snapshot','-i');line=next(x for x in snap.splitlines() if 'LabelText "Advanced"' in x)
        ab('click','@'+re.search(r'ref=(e\d+)',line).group(1))
    fill('combobox','API Endpoint','http://127.0.0.1:3438');ab('press','Tab')
    fill('textbox','API Key','sk-e2e-placeholder')
    fill('textbox','Custom Name','E2E-Mock')
    click('button','Models');ab('wait','--text','context e2e mock')
    close_dialog()

def select_context():
    open_preferences();click('button','Custom Search')
    click('combobox','Search provider');click('option','Context.dev')
    fill('textbox','Restrict to domain','context.dev')
    assert 'Already set on server' in body(),'Dev server must supply Context credential'
    assert 'Context.dev' in ab('snapshot','-i')
    ab('screenshot',str(ROOT/'context-selected.png'));close_dialog()
    ab('reload')
    ab('wait','--fn',"document.querySelector('textarea') !== null && document.body.innerText.includes('New chat')")
    open_preferences();click('button','Custom Search')
    snap=ab('snapshot','-i')
    assert 'combobox "Search provider"' in snap and ': Context.dev' in snap
    assert 'textbox "Restrict to domain"' in snap and ': context.dev' in snap
    (ROOT/'provider-persistence.txt').write_text(snap)
    close_dialog()

ab('open',URL)
ab('wait','--fn',"document.querySelector('textarea') !== null && document.body.innerText.includes('New chat')")
if 'context e2e mock' not in body():setup_model()
select_context()
click('button','New chat')
# No endpoint is mocked or intercepted. Network records retain only method/URL.
ab('network','requests','--clear')
urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:3438/__reset',data=b'',method='POST')).read()
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
fill('textbox','Type · drop files · /react · ramble...','/react What does Context.dev offer? Verify using its official website and cite the source.')
ab('press','Enter')
ab('wait','--text','Live retrieval verified.')
text=body()
evidence=json.loads(urllib.request.urlopen('http://127.0.0.1:3438/__evidence').read())
assert any(e['kind']=='search-action' for e in evidence),evidence
answers=[e for e in evidence if e['kind']=='grounded-answer']
assert answers and answers[-1]['source'].startswith('https://'),evidence
assert 'context.dev' in answers[-1]['source'],evidence
assert not any(e['kind']=='rejected-observation' for e in evidence),evidence
assert 'Live retrieval verified.' in text and 'E2E_FAILED' not in text
network=ab('network','requests','--filter','contextSearch.search')
assert 'contextSearch.search' in network,network
links=ab('eval',"JSON.stringify(Array.from(document.querySelectorAll('a[href]')).map(a=>({text:a.textContent,href:a.href})).filter(a=>a.href.includes('context.dev')))")
assert answers[-1]['source'] in links,links
(ROOT/'context-route-network.txt').write_text(network)
(ROOT/'answer.txt').write_text(text)
(ROOT/'source-links.json').write_text(links)
ab('screenshot',str(ROOT/'live-react-answer.png'))
summary={'passed':True,'gitHead':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'startedAt':started,'finishedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uiUrl':URL,'browserSession':SESSION,'model':'deterministic local mock','retrieval':'real Context API via application tRPC route','assertions':['provider selected through UI','provider/domain persist after reload','/react submitted through UI','real Context route requested','search action fed actual source observation to second model turn','mock refuses success without official source','answer and matching citation render in UI'],'source':answers[-1]['source'],'retrievedSourceCount':answers[-1]['sourceCount'],'limitation':'Validates integration, not real LLM answer quality.'}
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
