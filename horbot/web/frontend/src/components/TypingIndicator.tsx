import React, { memo } from 'react';

interface TypingIndicatorProps {
  agentNames: string[];
}

const TypingIndicator: React.FC<TypingIndicatorProps> = ({ agentNames }) => {
  if (agentNames.length === 0) return null;
  
  const text = agentNames.length === 1
    ? `${agentNames[0]} 正在输入...`
    : agentNames.length === 2
    ? `${agentNames[0]} 和 ${agentNames[1]} 正在输入...`
    : `${agentNames[0]} 和其他 ${agentNames.length - 1} 个 Agent 正在输入...`;
  
  return (
    <div className="flex items-center gap-2 px-4 py-2 text-surface-500 text-sm animate-fade-in">
      <div className="flex gap-1">
        <span className="w-2 h-2 bg-surface-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-2 h-2 bg-surface-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-2 h-2 bg-surface-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span>{text}</span>
    </div>
  );
};

export default memo(TypingIndicator);
