import React, { memo, useEffect, useRef, useState } from 'react';

interface AgentInfo {
  id: string;
  name: string;
  description: string;
  model: string;
  provider: string;
  capabilities: string[];
  teams: string[];
  is_main: boolean;
}

interface AgentMentionProps {
  agents: AgentInfo[];
  onSelect: (agent: AgentInfo) => void;
  onClose: () => void;
  position: { top: number; left: number };
  filter?: string;
}

// Agent 头像颜色映射（与 AgentSidebar 保持一致）
const getAgentColor = (agentId: string): { bg: string; text: string } => {
  const colors = [
    { bg: 'bg-gradient-to-br from-purple-400 to-purple-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-emerald-400 to-emerald-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-orange-400 to-orange-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-cyan-400 to-cyan-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-pink-400 to-pink-600', text: 'text-white' },
    { bg: 'bg-gradient-to-br from-indigo-400 to-indigo-600', text: 'text-white' },
  ];
  
  const index = Math.abs(agentId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)) % colors.length;
  return colors[index];
};

const AgentMention: React.FC<AgentMentionProps> = ({
  agents,
  onSelect,
  onClose,
  position,
  filter = '',
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // 过滤 Agent 列表
  const filteredAgents = agents.filter(agent =>
    agent.name.toLowerCase().includes(filter.toLowerCase()) ||
    agent.description?.toLowerCase().includes(filter.toLowerCase())
  );

  // 键盘导航
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev => 
            prev < filteredAgents.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => prev > 0 ? prev - 1 : prev);
          break;
        case 'Enter':
          e.preventDefault();
          if (filteredAgents[selectedIndex]) {
            onSelect(filteredAgents[selectedIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [filteredAgents, selectedIndex, onSelect, onClose]);

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (listRef.current && !listRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  // 滚动到选中项
  useEffect(() => {
    if (listRef.current) {
      const selectedElement = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex]);

  if (filteredAgents.length === 0) {
    return (
      <div
        ref={listRef}
        className="fixed z-50 bg-white rounded-xl shadow-xl border border-surface-200 py-2 px-3 min-w-[200px]"
        style={{ top: position.top, left: position.left }}
      >
        <p className="text-sm text-surface-500">没有匹配的 Agent</p>
      </div>
    );
  }

  return (
    <div
      ref={listRef}
      className="fixed z-50 bg-white rounded-xl shadow-xl border border-surface-200 py-1.5 min-w-[240px] max-h-[280px] overflow-y-auto"
      style={{ top: position.top, left: position.left }}
    >
      <div className="px-2 py-1.5 text-xs font-medium text-surface-500 border-b border-surface-100 mb-1">
        选择 Agent
      </div>
      
      {filteredAgents.map((agent, index) => {
        const color = getAgentColor(agent.id);
        const isSelected = index === selectedIndex;
        
        return (
          <button
            key={agent.id}
            data-index={index}
            onClick={() => onSelect(agent)}
            onMouseEnter={() => setSelectedIndex(index)}
            className={`w-full flex items-center gap-2.5 px-2.5 py-2 transition-all text-left ${
              isSelected ? 'bg-primary-50' : 'hover:bg-surface-50'
            }`}
          >
            {/* 头像 */}
            <div className={`w-7 h-7 rounded-lg ${color.bg} flex items-center justify-center ${color.text} font-semibold text-xs shadow-sm flex-shrink-0`}>
              {agent.name.charAt(0).toUpperCase()}
            </div>
            
            {/* 信息 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className={`text-sm font-medium truncate ${isSelected ? 'text-primary-700' : 'text-surface-900'}`}>
                  {agent.name}
                </span>
              </div>
              <p className="text-xs text-surface-500 truncate">{agent.description || agent.model}</p>
            </div>
            
            {/* 选中指示 */}
            {isSelected && (
              <svg className="w-4 h-4 text-primary-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
          </button>
        );
      })}
      
      <div className="px-2 py-1.5 text-xs text-surface-400 border-t border-surface-100 mt-1 flex items-center gap-2">
        <span>↑↓ 导航</span>
        <span>•</span>
        <span>Enter 选择</span>
        <span>•</span>
        <span>Esc 关闭</span>
      </div>
    </div>
  );
};

export default memo(AgentMention);

// 辅助函数：解析文本中的 @ 提及
export const parseMentions = (text: string, agents: AgentInfo[]): { text: string; mentions: string[] } => {
  const mentionRegex = /@(\w+)/g;
  const mentions: string[] = [];
  
  const processedText = text.replace(mentionRegex, (match: string, name: string) => {
    const agent = agents.find(a => a.name.toLowerCase() === name.toLowerCase());
    if (agent) {
      mentions.push(agent.id);
      return `@${agent.name}`;
    }
    return match;
  });
  
  return { text: processedText, mentions };
};

// 渲染带高亮的提及文本
export const renderMentionText = (text: string, agents: AgentInfo[]): React.ReactNode => {
  const mentionRegex = /@(\w+)/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let matchResult: RegExpExecArray | null = null;
  
  while ((matchResult = mentionRegex.exec(text)) !== null) {
    if (matchResult.index > lastIndex) {
      parts.push(text.slice(lastIndex, matchResult.index));
    }
    
    const agent = agents.find(a => a.name.toLowerCase() === matchResult![1].toLowerCase());
    if (agent) {
      const color = getAgentColor(agent.id);
      parts.push(
        <span
          key={matchResult.index}
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${color.bg} ${color.text} text-xs font-medium`}
        >
          @{agent.name}
        </span>
      );
    } else {
      parts.push(matchResult[0]);
    }
    
    lastIndex = matchResult.index + matchResult[0].length;
  }
  
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  
  return parts.length > 0 ? parts : text;
};
