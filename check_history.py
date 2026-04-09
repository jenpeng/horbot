import json
import urllib.request
import re

url = "http://localhost:8000/api/chat/history?session_key=web:session_1773105656"
with urllib.request.urlopen(url) as response:
    data = json.loads(response.read().decode())

messages = data.get('messages', [])
for i, msg in enumerate(messages):
    if msg.get('role') == 'user' and 'files' in msg:
        content = msg.get('content', '')
        files = msg.get('files', [])
        
        # Test regex
        import re
        # The regex should match from \n\n---\n**文档: to end of message
        pattern = r'\n\n---\n\*\*文档:.*?\*\*\n\n[\s\S]*$'
        new_content = re.sub(pattern, '', content).strip()
        
        print(f'User message {i}:')
        print(f'  Original content length: {len(content)}')
        print(f'  New content length: {len(new_content)}')
        print(f'  Original content preview: {content[:100]}')
        print(f'  New content preview: {new_content[:100]}')
        print(f'  Files count: {len(files)}')
        print()
        break
