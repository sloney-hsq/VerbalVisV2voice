import json

src = r'C:\Users\hsqsl\.claude\projects\C--VerbalVis-VerbalVis2\8bdc3ccb-6007-4c88-94d1-5f2ad42a4d90.jsonl'
dst = r'C:\VerbalVis\VerbalVis2\deepseek聊天记录输出.md'

with open(src, 'r', encoding='utf-8') as f_in, open(dst, 'w', encoding='utf-8') as out:
    out.write('# VerbalVis 对话记录\n\n')

    for l in f_in:
        try:
            m = json.loads(l.strip())
        except json.JSONDecodeError:
            continue

        t = m.get('type', '')
        if t == 'user':
            c = m.get('message', {}).get('content', '')
            if isinstance(c, str) and c.strip():
                out.write(f'## 用户\n\n{c}\n\n---\n\n')
        elif t == 'assistant':
            content = m.get('message', {}).get('content', [])
            if isinstance(content, list):
                parts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
                if parts:
                    out.write(f'## Claude\n\n{" ".join(parts)}\n\n---\n\n')

print(f'Done! {dst}')