import React, { memo, useState, useRef, useEffect } from 'react';

interface AgentInfo {
  id: string;
  name: string;
}

interface MentionPickerProps {
  agents: AgentInfo[];
  position: { top: number; left: number };
  onSelect: (agent: AgentInfo) => void;
  onClose: () => void;
  filter: string;
}

const MentionPicker: React.FC<MentionPickerProps> = ({
  agents,
  position,
  onSelect,
  onClose,
  filter,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  
  const filteredAgents = agents.filter(agent =>
    agent.name.toLowerCase().includes(filter.toLowerCase())
  );
  
  useEffect(() => {
    setSelectedIndex(0);
  }, [filter]);
  
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(prev => Math.min(prev + 1, filteredAgents.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(prev => Math.max(prev - 1, 0));
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
  
  useEffect(() => {
    if (listRef.current) {
      const selectedElement = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedElement) {
        selectedElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);
  
  if (filteredAgents.length === 0) {
    return (
      <div
        className="absolute z-50 bg-surface-800 border border-surface-600 rounded-lg shadow-xl p-2 text-sm text-surface-400"
        style={{ top: position.top, left: position.left }}
      >
        没有匹配的 Agent
      </div>
    );
  }
  
  return (
    <div
      ref={listRef}
      className="absolute z-50 bg-surface-800 border border-surface-600 rounded-lg shadow-xl max-h-48 overflow-y-auto min-w-[200px]"
      style={{ top: position.top, left: position.left }}
    >
      {filteredAgents.map((agent, index) => (
        <button
          key={agent.id}
          onClick={() => onSelect(agent)}
          className={`
            w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors
            ${index === selectedIndex
              ? 'bg-primary-500 text-white'
              : 'text-surface-200 hover:bg-surface-700'
            }
          `}
        >
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white text-xs font-semibold">
            {agent.name.charAt(0).toUpperCase()}
          </div>
          <span>{agent.name}</span>
        </button>
      ))}
    </div>
  );
};

export default memo(MentionPicker);
