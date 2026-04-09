import React, { useState, memo } from 'react';

interface ToolsPanelProps {
  isCollapsed?: boolean;
  onToggle?: () => void;
  className?: string;
}

// 简单的SVG图标组件
const FileIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

const FolderIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-accent-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
  </svg>
);

const SearchIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

const ToolsIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const ContextIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
  </svg>
);

const ZapIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const ListIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
  </svg>
);

const CloseIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const SettingsIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const ToolsPanel: React.FC<ToolsPanelProps> = ({ isCollapsed = false, onToggle, className = '' }) => {
  const [activeTab, setActiveTab] = useState<'files' | 'tools' | 'context' | 'search'>('files');
  const [workspacePath] = useState<string>('/workspace');
  const [fileStructure] = useState<any[]>([
    { name: 'README.md', type: 'file', path: '/README.md' },
    { name: 'src', type: 'folder', children: [
      { name: 'index.ts', type: 'file', path: '/src/index.ts' },
      { name: 'components', type: 'folder', children: [
        { name: 'Button.tsx', type: 'file', path: '/src/components/Button.tsx' },
        { name: 'Modal.tsx', type: 'file', path: '/src/components/Modal.tsx' },
      ]},
    ]},
    { name: 'docs', type: 'folder', children: [
      { name: 'guide.md', type: 'file', path: '/docs/guide.md' },
      { name: 'api.md', type: 'file', path: '/docs/api.md' },
    ]},
  ]);

  const [recentTools] = useState<Array<{name: string, lastUsed: string}>>([
    { name: 'read_file', lastUsed: '2分钟前' },
    { name: 'exec', lastUsed: '5分钟前' },
    { name: 'web_search', lastUsed: '10分钟前' },
    { name: 'edit_file', lastUsed: '15分钟前' },
    { name: 'list_dir', lastUsed: '20分钟前' },
  ]);

  const [contextItems] = useState<Array<{title: string, description: string, type: string}>>([
    { title: '当前会话', description: 'UI设计讨论', type: 'session' },
    { title: '工作空间', description: '/workspace', type: 'workspace' },
    { title: '可用技能', description: '12个已加载', type: 'skills' },
    { title: '内存上下文', description: 'L0 + L1 已加载', type: 'memory' },
  ]);

  const [searchQuery, setSearchQuery] = useState('');

  const handleFileClick = (file: any) => {
    console.log('File clicked:', file);
  };

  const handleToolClick = (toolName: string) => {
    console.log('Tool clicked:', toolName);
  };

  const renderFileItem = (item: any, depth: number = 0) => {
    const isFolder = item.type === 'folder';
    
    return (
      <div key={item.name} className="select-none">
        <div 
          className={`flex items-center gap-2 px-3 py-2 rounded-card cursor-pointer hover:bg-surface-700 transition-colors ${depth > 0 ? 'ml-6' : ''}`}
          onClick={() => isFolder ? {} : handleFileClick(item)}
        >
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div style={{ marginLeft: `${depth * 12}px` }} />
            {isFolder ? <FolderIcon /> : <FileIcon />}
            <span className="text-sm truncate">{item.name}</span>
          </div>
        </div>
        {isFolder && item.children && (
          <div className="ml-3 border-l border-surface-700">
            {item.children.map((child: any) => renderFileItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const tabs = [
    { id: 'files', label: '文件', icon: <FolderIcon /> },
    { id: 'tools', label: '工具', icon: <ToolsIcon /> },
    { id: 'context', label: '上下文', icon: <ContextIcon /> },
    { id: 'search', label: '搜索', icon: <SearchIcon /> },
  ];

  if (isCollapsed) {
    return (
      <div className={`flex flex-col h-full bg-surface-900 border-l border-surface-700 ${className}`}>
        <div className="p-4 border-b border-surface-700">
          <button
            onClick={onToggle}
            className="w-full flex items-center justify-center p-2 rounded-card bg-surface-800 hover:bg-surface-700 transition-colors"
            title="展开工具面板"
          >
            <ListIcon />
          </button>
        </div>
        <div className="flex-1 flex flex-col items-center py-4 space-y-4">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id as any);
                onToggle?.();
              }}
              className={`p-3 rounded-card transition-colors ${activeTab === tab.id ? 'bg-brand-500 text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}`}
              title={tab.label}
            >
              {tab.icon}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-surface-900 border-l border-surface-700 w-80 ${className}`}>
      {/* 面板头部 */}
      <div className="p-4 border-b border-surface-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-card bg-gradient-to-br from-brand-500 to-accent-purple flex items-center justify-center">
            <ZapIcon />
          </div>
          <div>
            <h3 className="font-semibold text-surface-100">工具面板</h3>
            <p className="text-xs text-surface-500">快速访问 & 上下文</p>
          </div>
        </div>
        <button
          onClick={onToggle}
          className="p-2 rounded-card hover:bg-surface-700 transition-colors text-surface-400 hover:text-surface-300"
          title="折叠面板"
        >
          <CloseIcon />
        </button>
      </div>

      {/* 标签导航 */}
      <div className="flex border-b border-surface-700">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm transition-colors relative ${activeTab === tab.id ? 'text-brand-400' : 'text-surface-400 hover:text-surface-300'}`}
          >
            {tab.icon}
            <span>{tab.label}</span>
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-t-full" />
            )}
          </button>
        ))}
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-hidden">
        {/* 文件浏览器 */}
        {activeTab === 'files' && (
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-surface-700">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-medium text-surface-200">工作空间</h4>
                <button className="text-xs text-brand-400 hover:text-brand-300">
                  <SettingsIcon />
                </button>
              </div>
              <div className="text-xs text-surface-500 bg-surface-800 px-3 py-2 rounded-card font-mono truncate">
                {workspacePath}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
              <div className="space-y-1">
                {fileStructure.map(item => renderFileItem(item))}
              </div>
            </div>
            <div className="p-3 border-t border-surface-700">
              <button className="w-full py-2 px-3 bg-surface-800 hover:bg-surface-700 rounded-card text-sm text-surface-300 flex items-center justify-center gap-2 transition-colors">
                <FolderIcon />
                打开文件夹
              </button>
            </div>
          </div>
        )}

        {/* 工具面板 */}
        {activeTab === 'tools' && (
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-surface-700">
              <h4 className="font-medium text-surface-200 mb-3">常用工具</h4>
              <div className="text-sm text-surface-400">点击工具快速调用</div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
              <div className="space-y-3">
                <h5 className="text-xs font-medium text-surface-500 uppercase tracking-wider mb-2">最近使用</h5>
                {recentTools.map(tool => (
                  <div
                    key={tool.name}
                    className="group flex items-center gap-3 p-3 rounded-card bg-surface-800 hover:bg-surface-700 cursor-pointer transition-all hover:shadow-md border border-surface-700 hover:border-brand-500"
                    onClick={() => handleToolClick(tool.name)}
                  >
                    <div className="w-8 h-8 rounded-card bg-brand-500/20 flex items-center justify-center text-brand-400">
                      <ToolsIcon />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-surface-200 truncate">{tool.name}</div>
                      <div className="text-xs text-surface-500">{tool.lastUsed}</div>
                    </div>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <div className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="mt-6">
                <h5 className="text-xs font-medium text-surface-500 uppercase tracking-wider mb-2">工具分类</h5>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { name: '文件操作', count: 8, color: 'text-accent-blue' },
                    { name: '网络工具', count: 5, color: 'text-accent-emerald' },
                    { name: '代码编辑', count: 6, color: 'text-accent-purple' },
                    { name: '数据分析', count: 4, color: 'text-accent-orange' },
                  ].map(category => (
                    <div
                      key={category.name}
                      className="p-3 rounded-card bg-surface-800 hover:bg-surface-700 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className={`${category.color}`}>
                          <ToolsIcon />
                        </div>
                        <span className="text-xs text-surface-500">{category.count}</span>
                      </div>
                      <div className="text-sm font-medium text-surface-200">{category.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 上下文面板 */}
        {activeTab === 'context' && (
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-surface-700">
              <h4 className="font-medium text-surface-200 mb-3">当前上下文</h4>
              <div className="text-sm text-surface-400">AI助手可用的信息和状态</div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
              <div className="space-y-3">
                {contextItems.map((item, index) => (
                  <div
                    key={index}
                    className="p-3 rounded-card bg-surface-800 border border-surface-700 hover:border-brand-500 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="font-medium text-surface-200">{item.title}</div>
                      <div className={`text-xs px-2 py-1 rounded-full ${item.type === 'session' ? 'bg-brand-500/20 text-brand-400' : 'bg-surface-500/20 text-surface-400'}`}>
                        {item.type}
                      </div>
                    </div>
                    <div className="text-sm text-surface-400">{item.description}</div>
                  </div>
                ))}
              </div>
              
              <div className="mt-6">
                <h5 className="text-xs font-medium text-surface-500 uppercase tracking-wider mb-2">内存层次</h5>
                <div className="space-y-2">
                  {[
                    { level: 'L0', name: '当前会话', description: '活跃对话和临时状态', size: '2.4KB' },
                    { level: 'L1', name: '近期记忆', description: '最近的任务和决策', size: '15.8KB' },
                    { level: 'L2', name: '长期记忆', description: '重要事实和用户偏好', size: '48.2KB' },
                  ].map(memory => (
                    <div
                      key={memory.level}
                      className="flex items-center gap-3 p-3 rounded-card bg-surface-800 hover:bg-surface-700 transition-colors"
                    >
                      <div className="w-10 h-10 rounded-card bg-gradient-to-br from-brand-500 to-accent-purple flex items-center justify-center font-bold text-white">
                        {memory.level}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-surface-200">{memory.name}</div>
                        <div className="text-xs text-surface-500 truncate">{memory.description}</div>
                      </div>
                      <div className="text-xs text-surface-400">{memory.size}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 搜索面板 */}
        {activeTab === 'search' && (
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-surface-700">
              <div className="relative">
                <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-surface-500">
                  <SearchIcon />
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索文件、工具、上下文..."
                  className="w-full pl-10 pr-4 py-2 bg-surface-800 border border-surface-700 rounded-card text-surface-100 placeholder-surface-500 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
              {searchQuery ? (
                <div className="space-y-3">
                  <div className="text-sm text-surface-400">搜索 "{searchQuery}" 的结果</div>
                  <div className="text-center py-8 text-surface-500">
                    <div className="mx-auto mb-4 opacity-50">
                      <SearchIcon />
                    </div>
                    <div>未找到匹配的结果</div>
                    <div className="text-sm mt-2">尝试不同的关键词</div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-surface-500">
                  <div className="mx-auto mb-4 opacity-50">
                    <SearchIcon />
                  </div>
                  <div>输入关键词开始搜索</div>
                  <div className="text-sm mt-2">可以搜索文件、工具、会话历史等</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 面板底部 */}
      <div className="p-3 border-t border-surface-700">
        <div className="flex items-center justify-between text-xs text-surface-500">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-semantic-success animate-pulse" />
            <span>系统正常</span>
          </div>
          <div>v0.1.4</div>
        </div>
      </div>
    </div>
  );
};

export default memo(ToolsPanel);