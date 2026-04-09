#!/usr/bin/env python3
"""
清理会话历史文件中的思考内容（<think > 标签）

这个脚本会：
1. 遍历所有会话文件
2. 从 content 字段中移除 <think > 标签中的思考内容
3. 保存修改后的文件
"""

import json
import re
import os
from pathlib import Path

THINK_PATTERN = re.compile(r'<think[^>]*>[\s\S]*?</think *>', re.IGNORECASE)

def strip_think_tags(content: str) -> str:
    """移除 content 中的 <think > 标签及其内容"""
    if not content:
        return content
    return THINK_PATTERN.sub('', content).strip()

def process_session_file(file_path: Path) -> tuple[int, int]:
    """
    处理单个会话文件
    
    Returns:
        tuple: (total_lines, modified_lines)
    """
    total_lines = 0
    modified_lines = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        total_lines += 1
        line = line.strip()
        if not line:
            continue
            
        try:
            data = json.loads(line)
            
            if 'content' in data and data['content']:
                original_content = data['content']
                cleaned_content = strip_think_tags(original_content)
                
                if original_content != cleaned_content:
                    data['content'] = cleaned_content
                    modified_lines += 1
            
            new_lines.append(json.dumps(data, ensure_ascii=False))
            
        except json.JSONDecodeError as e:
            print(f"  警告: 无法解析行 {total_lines}: {e}")
            new_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in new_lines:
            f.write(line + '\n')
    
    return total_lines, modified_lines

def main():
    sessions_dir = Path(__file__).parent / '.horbot' / 'agents' / 'main' / 'workspace' / 'sessions'
    
    if not sessions_dir.exists():
        print(f"错误: 会话目录不存在: {sessions_dir}")
        return
    
    session_files = list(sessions_dir.glob('*.jsonl'))
    
    if not session_files:
        print("没有找到会话文件")
        return
    
    print(f"找到 {len(session_files)} 个会话文件")
    print("-" * 50)
    
    total_files = 0
    total_lines = 0
    total_modified = 0
    
    for file_path in session_files:
        print(f"处理: {file_path.name}")
        lines, modified = process_session_file(file_path)
        
        total_files += 1
        total_lines += lines
        total_modified += modified
        
        print(f"  总行数: {lines}, 修改行数: {modified}")
    
    print("-" * 50)
    print(f"处理完成!")
    print(f"  处理文件数: {total_files}")
    print(f"  总行数: {total_lines}")
    print(f"  修改行数: {total_modified}")

if __name__ == '__main__':
    main()
