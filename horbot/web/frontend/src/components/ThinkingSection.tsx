import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface ThinkingSectionProps {
  content: string;
}

const ThinkingSection: React.FC<ThinkingSectionProps> = ({ content }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="mb-3 rounded-lg border border-purple-500/30 bg-purple-500/5 overflow-hidden">
      <div 
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-purple-500/10 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-purple-400">💭</span>
          <span className="text-sm font-medium text-purple-300">思考过程</span>
        </div>
        <svg 
          className={`h-4 w-4 text-purple-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} 
          fill="none" 
          viewBox="0 0 24 24" 
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
      
      {isExpanded && (
        <div className="px-3 py-2 border-t border-purple-500/20 bg-secondary-800/30">
          <div className="prose prose-sm prose-invert max-w-none text-gray-300">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};

export default ThinkingSection;
