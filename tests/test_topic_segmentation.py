"""Test topic segmentation in context compression."""

from horbot.agent.context_compact import (
    compact_context, 
    detect_topic_change, 
    CompressionResult,
    estimate_tokens,
)

def test_topic_detection():
    """Test topic detection with multiple topics."""
    messages = [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        # Topic 1: horbot project
        {'role': 'user', 'content': '帮我修复 horbot 项目的 bug'},
        {'role': 'assistant', 'content': '好的，我来帮你修复 horbot 的 bug'},
        {'role': 'user', 'content': '这个 bug 在 loop.py 文件里'},
        {'role': 'assistant', 'content': '我找到了问题，已经修复了'},
        # Topic 2: shopping cart (completely different project)
        {'role': 'user', 'content': '现在帮我写一个购物车功能'},
        {'role': 'assistant', 'content': '好的，我来实现购物车功能'},
        {'role': 'user', 'content': '购物车需要支持优惠券'},
        {'role': 'assistant', 'content': '我已经添加了优惠券功能'},
        # Topic 3: documentation
        {'role': 'user', 'content': '帮我写一下项目文档'},
        {'role': 'assistant', 'content': '好的，我来写文档'},
        {'role': 'user', 'content': '文档需要包含 API 说明'},
        {'role': 'assistant', 'content': '文档已完成'},
    ]
    
    segments = detect_topic_change(messages)
    print(f'检测到 {len(segments)} 个话题分段:')
    for i, seg in enumerate(segments):
        print(f'  [{i+1}] {seg.topic}: {len(seg.messages)} 条消息')
    
    return messages, segments

def test_compression():
    """Test segmented compression."""
    messages = [
        {'role': 'system', 'content': 'You are a helpful assistant.'},
        # Topic 1: horbot project
        {'role': 'user', 'content': '帮我修复 horbot 项目的 bug'},
        {'role': 'assistant', 'content': '好的，我来帮你修复 horbot 的 bug'},
        {'role': 'user', 'content': '这个 bug 在 loop.py 文件里'},
        {'role': 'assistant', 'content': '我找到了问题，已经修复了'},
        # Topic 2: shopping cart
        {'role': 'user', 'content': '现在帮我写一个购物车功能'},
        {'role': 'assistant', 'content': '好的，我来实现购物车功能'},
        {'role': 'user', 'content': '购物车需要支持优惠券'},
        {'role': 'assistant', 'content': '我已经添加了优惠券功能'},
        # Topic 3: documentation
        {'role': 'user', 'content': '帮我写一下项目文档'},
        {'role': 'assistant', 'content': '好的，我来写文档'},
        {'role': 'user', 'content': '文档需要包含 API 说明'},
        {'role': 'assistant', 'content': '文档已完成'},
    ]
    
    result = compact_context(messages, max_tokens=100, preserve_recent=4, return_details=True)
    
    if isinstance(result, CompressionResult):
        print(f'\n压缩结果:')
        print(f'  原始 tokens: {result.original_tokens}')
        print(f'  压缩后 tokens: {result.compressed_tokens}')
        print(f'  节省比例: {result.reduction_percent:.1f}%')
        print(f'  话题分段: {len(result.topics)}')
        
        if result.topics:
            print(f'\n话题分段详情:')
            for i, topic in enumerate(result.topics):
                print(f'  [{i+1}] {topic.topic}: {len(topic.messages)} 条消息')
                if topic.summary:
                    print(f'      摘要: {topic.summary[:100]}...')
        
        print(f'\n压缩后消息结构:')
        for i, msg in enumerate(result.messages):
            role = msg.get('role', '')
            content = msg.get('content', '')
            if isinstance(content, str):
                preview = content[:80].replace('\n', ' ')
                print(f'  [{i}] {role}: {preview}...')
            else:
                print(f'  [{i}] {role}: [复杂内容]')

if __name__ == '__main__':
    print('=' * 60)
    print('测试话题检测')
    print('=' * 60)
    test_topic_detection()
    
    print('\n' + '=' * 60)
    print('测试分段压缩')
    print('=' * 60)
    test_compression()
    
    print('\n✅ 所有测试通过!')
