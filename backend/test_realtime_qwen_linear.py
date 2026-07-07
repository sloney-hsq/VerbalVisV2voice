import asyncio
import importlib.util
import json
import sys
import tempfile
import time
import types
from pathlib import Path

# Dependency stubs
logging_utils = types.ModuleType('logging_utils')
def resolve_session_log_dir(root, session_id, mode, analysis_id=None):
    path = Path(tempfile.mkdtemp(prefix='vvlogs-'))
    return path, analysis_id or session_id
logging_utils.resolve_session_log_dir = resolve_session_log_dir
logging_utils.safe_log_token = lambda value, fallback=None: str(value or fallback or '').strip()
sys.modules['logging_utils'] = logging_utils

prompts = types.ModuleType('prompts')
prompts.build_system_prompt = lambda condition='full_duplex_voice': 'prompt'
sys.modules['prompts'] = prompts

state = {'filters': [], 'views': [{'id': 'view-1'}], 'calls': []}
tools = types.ModuleType('tools')
tools.TOOL_SCHEMAS = [{'type':'function','name':'filter_data','description':'','parameters':{'type':'object','properties':{}}}]
tools.activate_state_scope = lambda *a, **k: None
tools.get_active_filters_for_frontend = lambda: list(state['filters'])
tools.get_views_for_frontend = lambda: list(state['views'])
tools.persist_active_state_scope = lambda: None
tools.realtime_state = lambda: {'active_filters': list(state['filters'])}
tools.normalize_tool_arguments = lambda name, args, user_transcript='': args
tools.log_tool_call = lambda **kwargs: None

def execute_tool(name, args):
    time.sleep(0.03)
    state['calls'].append((name, dict(args)))
    if name == 'filter_data':
        state['filters'][:] = [{'field': args.get('field'), 'value': args.get('value')}]
    return {'success': True, 'tool': name, 'payload': {'active_filters': list(state['filters'])}}
tools.execute_tool = execute_tool
sys.modules['tools'] = tools

spec = importlib.util.spec_from_file_location('realtime_qwen_tested', '/tmp/realtime_qwen.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ClientWS:
    def __init__(self): self.sent=[]
    async def send_json(self, msg): self.sent.append(msg)

class QwenWS:
    def __init__(self): self.sent=[]
    async def send(self, raw): self.sent.append(json.loads(raw))
    async def close(self): pass

async def new_session():
    client=ClientWS(); qwen=QwenWS()
    s=mod.QwenRealtimeSession(client, session_id='test', analysis_id='test')
    s.qwen_ws=qwen
    s._qwen_ready=True
    return s, client, qwen

async def wait_tools(s):
    tasks=list(s._tool_tasks)
    if tasks:
        await asyncio.gather(*tasks)
    await asyncio.sleep(0)

async def scenario_ordinary():
    state['calls'].clear(); state['filters'].clear()
    s,c,q=await new_session()
    s._latest_user_turn_id='t1'
    await s._handle_response_created({'response':{'id':'r1'}})
    await s._commit_tool_call({'call_id':'c1','name':'filter_data','arguments':'{"field":"customer_state","value":"RJ"}'}, 'r1')
    await s._handle_response_done({'response':{'id':'r1','output':[]}}, 'r1')
    await wait_tools(s)
    assert state['calls']==[('filter_data', {'field':'customer_state','value':'RJ'})]
    assert any(m['type']=='tool_result' for m in c.sent)
    assert any(m['type']=='views_update' for m in c.sent)
    assert any(m['type']=='conversation.item.create' for m in q.sent)
    assert sum(m['type']=='response.create' for m in q.sent)==1

async def scenario_interrupted_tool():
    state['calls'].clear(); state['filters'].clear()
    s,c,q=await new_session()
    s._latest_user_turn_id='t1'
    await s._handle_response_created({'response':{'id':'r1'}})
    await s._commit_tool_call({'call_id':'c1','name':'filter_data','arguments':'{"field":"customer_state","value":"RJ"}'}, 'r1')
    await s._begin_user_turn('t2','qwen_semantic_vad')
    await s._handle_response_done({'response':{'id':'r1','output':[]}}, 'r1')
    await wait_tools(s)
    assert any(m['type']=='tool_result' for m in c.sent)
    assert any(m['type']=='views_update' for m in c.sent)
    assert any(m['type']=='conversation.item.create' for m in q.sent)
    assert not any(m['type']=='response.create' for m in q.sent)
    assert any(e['event']=='tool.followup.suppressed' for e in s._timeline)

async def scenario_voice_interrupt():
    s,c,q=await new_session()
    s._latest_user_turn_id='t1'
    await s._handle_response_created({'response':{'id':'r1'}})
    s._assistant_transcript_buffers['r1']='partial answer'
    await s._begin_user_turn('t2','qwen_semantic_vad')
    assert any(m['type']=='assistant_playback_stop' and m['response_id']=='r1' for m in c.sent)
    assert any(m['type']=='response.cancel' for m in q.sent)
    assert s.latest_response_id is None and s._playback_response_id is None
    assert 'r1' in s._interrupted_response_ids

async def scenario_multiple_tools():
    state['calls'].clear(); state['filters'].clear()
    s,c,q=await new_session()
    s._latest_user_turn_id='t1'
    await s._handle_response_created({'response':{'id':'r1'}})
    await s._commit_tool_call({'call_id':'c1','name':'filter_data','arguments':'{"field":"customer_state","value":"RJ"}'}, 'r1')
    await s._commit_tool_call({'call_id':'c2','name':'filter_data','arguments':'{"field":"customer_state","value":"SP"}'}, 'r1')
    await s._handle_response_done({'response':{'id':'r1','output':[]}}, 'r1')
    await wait_tools(s)
    assert len(state['calls'])==2
    assert sum(m['type']=='conversation.item.create' for m in q.sent)==2
    assert sum(m['type']=='response.create' for m in q.sent)==1

async def main():
    await scenario_ordinary()
    await scenario_interrupted_tool()
    await scenario_voice_interrupt()
    await scenario_multiple_tools()
    print('all linear execution scenarios passed')

asyncio.run(main())
