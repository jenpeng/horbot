import React, { Suspense, lazy, useState, useEffect, useMemo } from 'react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button, IconButton } from '../components/ui/Button';
import Tabs from '../components/ui/Tabs';
import skillsService from '../services/skills';
import type { Skill, SkillDetail, MCPServerConfig } from '../types';

const MarkdownRenderer = lazy(() => import('../components/MarkdownRenderer'));

interface SkillEditorState {
  isOpen: boolean;
  mode: 'create' | 'edit';
  skillName: string;
  content: string;
  originalContent: string;
}

interface MCPServerEditorState {
  isOpen: boolean;
  mode: 'create' | 'edit';
  name: string;
  command: string;
  args: string;
  url: string;
  env: string;
  tool_timeout: number;
  originalData: MCPServerConfig | null;
}

const markdownPreviewFallback = (
  <div className="rounded-xl border border-surface-200 bg-white/70 px-4 py-6 text-sm text-surface-500">
    正在加载 Markdown 预览...
  </div>
);

const SkillsPage: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [mcpServers, setMcpServers] = useState<Record<string, MCPServerConfig>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'skills' | 'mcp'>('skills');
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null);
  const [editor, setEditor] = useState<SkillEditorState>({
    isOpen: false,
    mode: 'create',
    skillName: '',
    content: '',
    originalContent: ''
  });
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [showPreview, setShowPreview] = useState(true);
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [mcpEditor, setMcpEditor] = useState<MCPServerEditorState>({
    isOpen: false,
    mode: 'create',
    name: '',
    command: '',
    args: '',
    url: '',
    env: '',
    tool_timeout: 120,
    originalData: null,
  });
  const [mcpDeleteConfirm, setMcpDeleteConfirm] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [skillsData, mcpData] = await Promise.all([
        skillsService.getSkills(),
        skillsService.getMcpServers()
      ]);
      setSkills(skillsData || []);
      setMcpServers(mcpData || {});
      setError(null);
    } catch (err) {
      setError('Failed to fetch data');
      console.error('Error fetching data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000);
  };

  const filteredSkills = useMemo(() => {
    if (!searchQuery) return skills;
    const query = searchQuery.toLowerCase();
    return skills.filter(skill => 
      skill.name.toLowerCase().includes(query) ||
      skill.description.toLowerCase().includes(query)
    );
  }, [skills, searchQuery]);

  const fetchSkillDetail = async (skillName: string) => {
    try {
      const data = await skillsService.getSkill(skillName);
      setSelectedSkill(data);
    } catch (err) {
      console.error('Error fetching skill detail:', err);
    }
  };

  const openCreateEditor = () => {
    setEditor({
      isOpen: true,
      mode: 'create',
      skillName: '',
      content: '# My Skill\n\nDescription of what this skill does.\n\n## Instructions\n\n- Step 1\n- Step 2\n',
      originalContent: ''
    });
    setShowPreview(true);
  };

  const openEditEditor = async (skill: Skill) => {
    try {
      const data = await skillsService.getSkill(skill.name);
      setEditor({
        isOpen: true,
        mode: 'edit',
        skillName: skill.name,
        content: data.content,
        originalContent: data.content
      });
      setSelectedSkill(null);
      setShowPreview(true);
    } catch (err) {
      console.error('Error fetching skill for edit:', err);
      showNotification('error', 'Failed to load skill for editing');
    }
  };

  const closeEditor = () => {
    setEditor({
      isOpen: false,
      mode: 'create',
      skillName: '',
      content: '',
      originalContent: ''
    });
  };

  const hasChanges = editor.content !== editor.originalContent;

  const saveSkill = async () => {
    if (!editor.skillName.trim() || !editor.content.trim()) {
      showNotification('error', 'Name and content are required');
      return;
    }

    setSaving(true);
    try {
      if (editor.mode === 'create') {
        await skillsService.createSkill({
          name: editor.skillName.trim(),
          content: editor.content
        });
        showNotification('success', `Skill '${editor.skillName}' created successfully`);
      } else {
        await skillsService.updateSkill(editor.skillName, {
          content: editor.content
        });
        showNotification('success', `Skill '${editor.skillName}' updated successfully`);
      }
      closeEditor();
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to save skill';
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (skillName: string) => {
    setSaving(true);
    try {
      await skillsService.deleteSkill(skillName);
      showNotification('success', `Skill '${skillName}' deleted successfully`);
      setDeleteConfirm(null);
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to delete skill';
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (skillName: string, _currentEnabled: boolean) => {
    try {
      const newEnabled = await skillsService.toggleSkill(skillName);
      showNotification('success', `Skill '${skillName}' ${newEnabled ? 'enabled' : 'disabled'} successfully`);
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to toggle skill';
      showNotification('error', message);
    }
  };

  const handleBatchToggle = async (enable: boolean) => {
    const skillsToToggle = Array.from(selectedSkills);
    setSaving(true);
    try {
      await Promise.all(
        skillsToToggle.map(skillName => {
          const skill = skills.find(s => s.name === skillName);
          if (skill && skill.enabled !== enable) {
            return skillsService.toggleSkill(skillName);
          }
          return Promise.resolve();
        })
      );
      showNotification('success', `${skillsToToggle.length} skills ${enable ? 'enabled' : 'disabled'} successfully`);
      setSelectedSkills(new Set());
      fetchData();
    } catch (err: any) {
      showNotification('error', 'Failed to toggle some skills');
    } finally {
      setSaving(false);
    }
  };

  const toggleSkillSelection = (skillName: string) => {
    const newSelected = new Set(selectedSkills);
    if (newSelected.has(skillName)) {
      newSelected.delete(skillName);
    } else {
      newSelected.add(skillName);
    }
    setSelectedSkills(newSelected);
  };

  const selectAllSkills = () => {
    if (selectedSkills.size === filteredSkills.length) {
      setSelectedSkills(new Set());
    } else {
      setSelectedSkills(new Set(filteredSkills.map(s => s.name)));
    }
  };

  const openMcpEditor = (name?: string, config?: MCPServerConfig) => {
    if (name && config) {
      setMcpEditor({
        isOpen: true,
        mode: 'edit',
        name,
        command: config.command || '',
        args: config.args?.join(' ') || '',
        url: config.url || '',
        env: config.env ? JSON.stringify(config.env, null, 2) : '',
        tool_timeout: config.tool_timeout || 120,
        originalData: config,
      });
    } else {
      setMcpEditor({
        isOpen: true,
        mode: 'create',
        name: '',
        command: '',
        args: '',
        url: '',
        env: '',
        tool_timeout: 120,
        originalData: null,
      });
    }
  };

  const closeMcpEditor = () => {
    setMcpEditor({
      isOpen: false,
      mode: 'create',
      name: '',
      command: '',
      args: '',
      url: '',
      env: '',
      tool_timeout: 120,
      originalData: null,
    });
  };

  const saveMcpServer = async () => {
    if (!mcpEditor.name.trim()) {
      showNotification('error', 'Server name is required');
      return;
    }
    if (!mcpEditor.command.trim() && !mcpEditor.url.trim()) {
      showNotification('error', 'Command or URL is required');
      return;
    }

    setSaving(true);
    try {
      let env: Record<string, string> | undefined;
      if (mcpEditor.env.trim()) {
        try {
          env = JSON.parse(mcpEditor.env);
        } catch {
          showNotification('error', 'Invalid JSON format for environment variables');
          setSaving(false);
          return;
        }
      }

      const config: MCPServerConfig = {
        command: mcpEditor.command.trim() || undefined,
        args: mcpEditor.args.trim() ? mcpEditor.args.trim().split(/\s+/) : undefined,
        url: mcpEditor.url.trim() || undefined,
        env,
        tool_timeout: mcpEditor.tool_timeout,
      };

      if (mcpEditor.mode === 'create') {
        await skillsService.addMcpServer(mcpEditor.name.trim(), config);
        showNotification('success', `MCP Server '${mcpEditor.name}' created successfully`);
      } else {
        await skillsService.updateMcpServer(mcpEditor.name.trim(), config);
        showNotification('success', `MCP Server '${mcpEditor.name}' updated successfully`);
      }
      closeMcpEditor();
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to save MCP server';
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const deleteMcpServer = async (name: string) => {
    setSaving(true);
    try {
      await skillsService.deleteMcpServer(name);
      showNotification('success', `MCP Server '${name}' deleted successfully`);
      setMcpDeleteConfirm(null);
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to delete MCP server';
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full bg-surface-100">
        <div className="flex flex-col items-center gap-4">
          <div className="flex space-x-2">
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
          <p className="text-surface-600 text-sm">Loading skills...</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'skills', label: `Skills (${skills.length})`, icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    )},
    { id: 'mcp', label: `MCP Servers (${Object.keys(mcpServers).length})`, icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
      </svg>
    )},
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-gradient-to-b from-surface-50 to-surface-100">
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6 w-full overflow-y-auto">
        {notification && (
          <div className={`fixed top-4 right-4 z-50 px-5 py-3 rounded-xl shadow-lg animate-slide-in-right ${
            notification.type === 'success' 
              ? 'bg-semantic-success-light border border-semantic-success/20 text-semantic-success' 
              : 'bg-semantic-error-light border border-semantic-error/20 text-semantic-error'
          }`}>
            <div className="flex items-center gap-2">
              {notification.type === 'success' ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {notification.message}
            </div>
          </div>
        )}

        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-bold text-surface-900">Skills & MCP</h2>
              <p className="text-sm text-surface-600 mt-1">Manage your AI skills and MCP server connections</p>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={fetchData}
                disabled={isLoading}
                leftIcon={
                  <svg 
                    xmlns="http://www.w3.org/2000/svg" 
                    className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} 
                    fill="none" 
                    viewBox="0 0 24 24" 
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                }
              >
                Refresh
              </Button>
              {activeTab === 'skills' && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={openCreateEditor}
                  leftIcon={
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  }
                >
                  New Skill
                </Button>
              )}
              {activeTab === 'mcp' && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => openMcpEditor()}
                  leftIcon={
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  }
                >
                  Add MCP Server
                </Button>
              )}
            </div>
          </div>
        </div>

        <Tabs
          tabs={tabs}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as 'skills' | 'mcp')}
          variant="underline"
        />

        {error && (
          <div className="bg-semantic-error-light border border-semantic-error/20 text-semantic-error p-4 rounded-xl">
            <div className="flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {error}
            </div>
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="space-y-4">
            {skills.length > 0 && (
              <div className="flex items-center gap-4 p-4 bg-white rounded-xl border border-surface-200 shadow-sm">
                <div className="relative flex-1 max-w-md">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search skills..."
                    className="w-full pl-10 pr-4 py-2 bg-surface-50 border border-surface-200 rounded-lg text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={selectAllSkills}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    {selectedSkills.size === filteredSkills.length ? 'Deselect All' : 'Select All'}
                  </button>
                  {selectedSkills.size > 0 && (
                    <>
                      <span className="text-surface-300">|</span>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleBatchToggle(true)}
                        disabled={saving}
                      >
                        Enable ({selectedSkills.size})
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleBatchToggle(false)}
                        disabled={saving}
                      >
                        Disable ({selectedSkills.size})
                      </Button>
                    </>
                  )}
                </div>
              </div>
            )}

            {filteredSkills.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 bg-white rounded-xl border border-surface-200 shadow-sm">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary-500 to-accent-indigo flex items-center justify-center mb-4">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <p className="text-surface-600 mb-4 font-medium">No skills found</p>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={openCreateEditor}
                  leftIcon={
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  }
                >
                  Create Your First Skill
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {filteredSkills.map((skill) => (
                  <Card
                    key={skill.name}
                    padding="none"
                    hover={!skill.available || !skill.enabled ? false : true}
                    className={`group relative overflow-hidden transition-all duration-300 ${
                      !skill.available || !skill.enabled 
                        ? 'opacity-75' 
                        : 'hover:shadow-card-hover hover:-translate-y-0.5'
                    } ${selectedSkills.has(skill.name) ? 'ring-2 ring-primary-500' : ''}`}
                  >
                    <div className={`absolute inset-0 bg-gradient-to-br ${
                      skill.enabled && skill.available
                        ? 'from-primary-500/5 via-transparent to-accent-purple/5' 
                        : 'from-surface-100 via-transparent to-surface-100'
                    } opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                    
                    <div className="p-5 relative z-10">
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex items-start gap-3 flex-1 min-w-0">
                          <input
                            type="checkbox"
                            checked={selectedSkills.has(skill.name)}
                            onChange={() => toggleSkillSelection(skill.name)}
                            className="mt-1 w-4 h-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <h3 
                                className="font-semibold text-surface-900 truncate cursor-pointer hover:text-primary-600 transition-colors"
                                onClick={() => fetchSkillDetail(skill.name)}
                              >
                                {skill.name}
                              </h3>
                              {skill.source === 'builtin' && (
                                <div className="flex-shrink-0 w-5 h-5 rounded-full bg-gradient-to-br from-primary-500 to-accent-indigo flex items-center justify-center">
                                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                  </svg>
                                </div>
                              )}
                            </div>
                            <p 
                              className="text-sm text-surface-600 line-clamp-2 cursor-pointer hover:text-surface-900 transition-colors"
                              onClick={() => fetchSkillDetail(skill.name)}
                            >
                              {skill.description}
                            </p>
                          </div>
                        </div>
                        
                        <button
                          onClick={(e) => { e.stopPropagation(); handleToggle(skill.name, skill.enabled); }}
                          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-all duration-300 flex-shrink-0 ${
                            skill.enabled 
                              ? 'bg-gradient-to-r from-accent-emerald to-accent-teal shadow-lg shadow-accent-emerald/20' 
                              : 'bg-surface-300 hover:bg-surface-400'
                          }`}
                          title={skill.enabled ? 'Click to disable' : 'Click to enable'}
                        >
                          <span
                            className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-all duration-300 ${
                              skill.enabled ? 'translate-x-5' : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </div>

                      <div className="flex items-center justify-between gap-3 pt-3 border-t border-surface-100">
                        <div className="flex items-center gap-2 flex-wrap">
                          {!skill.available && (
                            <Badge variant="error" size="sm">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                              </svg>
                              Missing
                            </Badge>
                          )}
                          {skill.always && (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-accent-purple/10 text-accent-purple">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              Always
                            </span>
                          )}
                          {skill.normalized_from_legacy && (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-accent-amber/15 text-accent-amber">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              {skill.source_schema}
                            </span>
                          )}
                          {skill.source === 'user' && (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-primary-100 text-primary-700">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                              </svg>
                              Custom
                            </span>
                          )}
                        </div>
                        {skill.source === 'user' && (
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <IconButton
                              variant="ghost"
                              size="sm"
                              onClick={(e) => { e.stopPropagation(); openEditEditor(skill); }}
                              className="text-surface-500 hover:text-primary-600 hover:bg-primary-50"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </IconButton>
                            <IconButton
                              variant="ghost"
                              size="sm"
                              onClick={(e) => { e.stopPropagation(); setDeleteConfirm(skill.name); }}
                              className="text-surface-500 hover:text-semantic-error hover:bg-semantic-error-light"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </IconButton>
                          </div>
                        )}
                      </div>

                      {skill.missing_requirements && Array.isArray(skill.missing_requirements) && skill.missing_requirements.length > 0 && (
                        <div className="mt-3 bg-semantic-error-light border border-semantic-error/20 rounded-lg p-3">
                          <p className="text-xs text-semantic-error flex items-start gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span><strong>Missing:</strong> {skill.missing_requirements.join(', ')}</span>
                          </p>
                        </div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'mcp' && (
          <div className="space-y-4">
            {Object.keys(mcpServers).length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 bg-white rounded-xl border border-surface-200 shadow-sm">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-accent-purple to-accent-pink flex items-center justify-center mb-4">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                  </svg>
                </div>
                <p className="text-surface-600 font-medium">No MCP servers configured</p>
                <p className="text-sm text-surface-500 mt-1">Add MCP servers to extend AI capabilities</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {Object.entries(mcpServers).map(([name, server]) => (
                  <Card key={name} padding="md" hover className="group">
                    <div className="flex items-start justify-between gap-3 mb-4">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-accent-purple to-accent-pink flex items-center justify-center flex-shrink-0">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                          </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-surface-900 truncate">{name}</h3>
                          <p className="text-sm text-surface-500 truncate mt-0.5">
                            {server.command ? `${server.command} ${server.args?.join(' ') || ''}` : server.url}
                          </p>
                        </div>
                      </div>
                      {server.tool_timeout && (
                        <Badge variant="default" size="sm">
                          {server.tool_timeout}s
                        </Badge>
                      )}
                      {server.has_secret_values && (
                        <Badge variant="warning" size="sm">
                          Secret Hidden
                        </Badge>
                      )}
                    </div>

                    {server.env && Object.keys(server.env).length > 0 && (
                      <div className="pt-3 border-t border-surface-100">
                        <p className="text-xs font-medium text-surface-500 mb-2 flex items-center gap-1">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                          </svg>
                          Environment Variables
                        </p>
                        <div className="space-y-1">
                          {Object.entries(server.env).slice(0, 3).map(([key, value]) => (
                            <div key={key} className="flex justify-between text-xs bg-surface-50 rounded-lg px-3 py-1.5">
                              <span className="text-primary-600 font-mono font-medium">{key}</span>
                              <span className="text-surface-400">{value ? '•••••••••' : '(empty)'}</span>
                            </div>
                          ))}
                          {Object.keys(server.env).length > 3 && (
                            <p className="text-xs text-surface-400 mt-1 text-center">+{Object.keys(server.env).length - 3} more...</p>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="mt-3 pt-3 border-t border-surface-100 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></div>
                        <span className="text-xs text-surface-500">Active</span>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <IconButton
                          variant="ghost"
                          size="sm"
                          onClick={() => openMcpEditor(name, server)}
                          className="text-surface-500 hover:text-primary-600 hover:bg-primary-50"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </IconButton>
                        <IconButton
                          variant="ghost"
                          size="sm"
                          onClick={() => setMcpDeleteConfirm(name)}
                          className="text-surface-500 hover:text-semantic-error hover:bg-semantic-error-light"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </IconButton>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {selectedSkill && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in" onClick={() => setSelectedSkill(null)}>
            <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden shadow-2xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-surface-200 bg-gradient-to-r from-surface-50 to-white">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-accent-indigo flex items-center justify-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-surface-900">{selectedSkill.name}</h3>
                      <div className="flex gap-2 mt-2">
                        {selectedSkill.always && (
                          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-accent-purple/10 text-accent-purple">
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Always Active
                          </span>
                        )}
                        <Badge variant={selectedSkill.available ? 'success' : 'error'} size="sm">
                          {selectedSkill.available ? (
                            <>
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              Available
                            </>
                          ) : (
                            <>
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                              Unavailable
                            </>
                          )}
                        </Badge>
                        <Badge variant="default" size="sm">
                          {selectedSkill.schema} v{selectedSkill.schema_version ?? 'n/a'}
                        </Badge>
                        {selectedSkill.normalized_from_legacy && (
                          <Badge variant="warning" size="sm">
                            From {selectedSkill.source_schema} v{selectedSkill.source_schema_version ?? 'n/a'}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <IconButton
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedSkill(null)}
                    className="text-surface-400 hover:text-surface-600"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </IconButton>
                </div>
              </div>

              <div className="p-6 overflow-y-auto max-h-[calc(85vh-120px)]">
                {Object.keys(selectedSkill.metadata).length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Metadata
                    </h4>
                    <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                      {Object.entries(selectedSkill.metadata).map(([key, value]) => (
                        <div key={key} className="flex gap-3 mb-2 last:mb-0">
                          <span className="text-primary-600 font-medium min-w-[120px]">{key}:</span>
                          <span className="text-surface-700">{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <h4 className="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Content
                  </h4>
                  <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                    <Suspense fallback={markdownPreviewFallback}>
                      <MarkdownRenderer content={selectedSkill.content} theme="light" />
                    </Suspense>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {editor.isOpen && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in" onClick={closeEditor}>
            <div className="bg-white rounded-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden shadow-2xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-surface-200 bg-gradient-to-r from-surface-50 to-white">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-purple to-accent-pink flex items-center justify-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-surface-900">
                        {editor.mode === 'create' ? 'Create New Skill' : `Edit: ${editor.skillName}`}
                      </h3>
                      <p className="text-sm text-surface-500 mt-1">
                        {editor.mode === 'create' ? 'Write a new skill in Markdown' : 'Modify the skill content'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasChanges && (
                      <span className="text-xs text-semantic-warning bg-semantic-warning-light px-2 py-1 rounded-full">
                        Unsaved changes
                      </span>
                    )}
                    <IconButton
                      variant="ghost"
                      size="sm"
                      onClick={closeEditor}
                      className="text-surface-400 hover:text-surface-600"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </IconButton>
                  </div>
                </div>
              </div>

              <div className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                {editor.mode === 'create' && (
                  <div>
                    <label className="block text-sm font-semibold text-surface-700 mb-2">
                      Skill Name
                    </label>
                    <input
                      type="text"
                      value={editor.skillName}
                      onChange={(e) => setEditor({ ...editor, skillName: e.target.value })}
                      placeholder="my-skill"
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-semibold text-surface-700">
                      Content (Markdown)
                    </label>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setShowPreview(!showPreview)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                          showPreview 
                            ? 'bg-primary-100 text-primary-700' 
                            : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
                        }`}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                        Preview
                      </button>
                    </div>
                  </div>
                  
                  <div className={`grid ${showPreview ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
                    <div className="relative">
                      <textarea
                        value={editor.content}
                        onChange={(e) => setEditor({ ...editor, content: e.target.value })}
                        placeholder="# My Skill&#10;&#10;Description...&#10;&#10;## Instructions&#10;&#10;- Step 1"
                        rows={20}
                        className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 font-mono text-sm placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 resize-none transition-all"
                      />
                    </div>
                    {showPreview && (
                      <div className="bg-surface-50 border border-surface-200 rounded-xl p-4 overflow-y-auto max-h-[500px]">
                        <div className="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">Preview</div>
                        <Suspense fallback={markdownPreviewFallback}>
                          <MarkdownRenderer content={editor.content} theme="light" />
                        </Suspense>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-surface-200 bg-surface-50 flex justify-between items-center">
                <div className="flex items-center gap-2 text-sm text-surface-500">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Supports Markdown formatting
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={closeEditor}
                  >
                    Cancel
                  </Button>
                  {hasChanges && editor.mode === 'edit' && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setEditor({ ...editor, content: editor.originalContent })}
                      disabled={saving}
                    >
                      Revert
                    </Button>
                  )}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={saveSkill}
                    isLoading={saving}
                    disabled={!editor.skillName.trim() || !editor.content.trim()}
                  >
                    {editor.mode === 'create' ? 'Create' : 'Save Changes'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {deleteConfirm && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in" onClick={() => setDeleteConfirm(null)}>
            <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
              <div className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 bg-semantic-error-light rounded-full">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-semantic-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-surface-900">Delete Skill</h3>
                    <p className="text-sm text-surface-500">This action cannot be undone</p>
                  </div>
                </div>
                <p className="text-surface-700 mb-6">
                  Are you sure you want to delete <span className="font-semibold text-primary-600">{deleteConfirm}</span>?
                </p>
                <div className="flex justify-end gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setDeleteConfirm(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(deleteConfirm)}
                    isLoading={saving}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {mcpEditor.isOpen && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in" onClick={closeMcpEditor}>
            <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
              <div className="p-6 border-b border-surface-200 bg-gradient-to-r from-surface-50 to-white">
                <div className="flex justify-between items-start">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-purple to-accent-pink flex items-center justify-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-surface-900">
                        {mcpEditor.mode === 'create' ? 'Add MCP Server' : `Edit: ${mcpEditor.name}`}
                      </h3>
                      <p className="text-sm text-surface-500 mt-1">
                        {mcpEditor.mode === 'create' ? 'Configure a new MCP server connection' : 'Modify the MCP server configuration'}
                      </p>
                    </div>
                  </div>
                  <IconButton
                    variant="ghost"
                    size="sm"
                    onClick={closeMcpEditor}
                    className="text-surface-400 hover:text-surface-600"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </IconButton>
                </div>
              </div>

              <div className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-180px)]">
                {mcpEditor.mode === 'create' && (
                  <div>
                    <label className="block text-sm font-semibold text-surface-700 mb-2">
                      Server Name <span className="text-semantic-error">*</span>
                    </label>
                    <input
                      type="text"
                      value={mcpEditor.name}
                      onChange={(e) => setMcpEditor({ ...mcpEditor, name: e.target.value })}
                      placeholder="browser"
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                    <p className="text-xs text-surface-500 mt-1">A unique identifier for this MCP server</p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-surface-700 mb-2">
                      Command
                    </label>
                    <input
                      type="text"
                      value={mcpEditor.command}
                      onChange={(e) => setMcpEditor({ ...mcpEditor, command: e.target.value })}
                      placeholder="python"
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                    <p className="text-xs text-surface-500 mt-1">The command to run (e.g., python, npx)</p>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-surface-700 mb-2">
                      Arguments
                    </label>
                    <input
                      type="text"
                      value={mcpEditor.args}
                      onChange={(e) => setMcpEditor({ ...mcpEditor, args: e.target.value })}
                      placeholder="-m horbot.mcp.browser.server"
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                    <p className="text-xs text-surface-500 mt-1">Space-separated arguments</p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-surface-700 mb-2">
                    URL (alternative to command)
                  </label>
                  <input
                    type="text"
                    value={mcpEditor.url}
                    onChange={(e) => setMcpEditor({ ...mcpEditor, url: e.target.value })}
                    placeholder="http://localhost:8080/mcp"
                    className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  />
                  <p className="text-xs text-surface-500 mt-1">For HTTP-based MCP servers (leave empty if using command)</p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-surface-700 mb-2">
                    Environment Variables (JSON)
                  </label>
                  <textarea
                    value={mcpEditor.env}
                    onChange={(e) => setMcpEditor({ ...mcpEditor, env: e.target.value })}
                    placeholder='{"API_KEY": "your-key-here"}'
                    rows={4}
                    className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 font-mono text-sm placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 resize-none transition-all"
                  />
                  <p className="text-xs text-surface-500 mt-1">
                    JSON object with environment variables
                    {mcpEditor.mode === 'edit' && mcpEditor.originalData?.has_secret_values
                      ? '。出于安全原因，已保存的敏感值不会回显；如需修改，请重新填写完整 JSON。'
                      : ''}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-surface-700 mb-2">
                    Tool Timeout (seconds)
                  </label>
                  <input
                    type="number"
                    value={mcpEditor.tool_timeout}
                    onChange={(e) => setMcpEditor({ ...mcpEditor, tool_timeout: parseInt(e.target.value) || 120 })}
                    placeholder="120"
                    min={10}
                    max={600}
                    className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  />
                  <p className="text-xs text-surface-500 mt-1">Maximum time to wait for tool execution</p>
                </div>

                <div className="bg-primary-50 rounded-xl p-4 border border-primary-100">
                  <h4 className="text-sm font-semibold text-primary-700 mb-2 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Built-in MCP Servers
                  </h4>
                  <div className="space-y-2 text-xs text-primary-600">
                    <p><strong>browser:</strong> python3 -m horbot.mcp.browser.server</p>
                    <p><strong>excel:</strong> python3 -m horbot.mcp.excel.server</p>
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-surface-200 bg-surface-50 flex justify-between items-center">
                <div className="flex items-center gap-2 text-sm text-surface-500">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Command or URL is required
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={closeMcpEditor}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={saveMcpServer}
                    isLoading={saving}
                    disabled={!mcpEditor.name.trim() || (!mcpEditor.command.trim() && !mcpEditor.url.trim())}
                  >
                    {mcpEditor.mode === 'create' ? 'Add Server' : 'Save Changes'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {mcpDeleteConfirm && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in" onClick={() => setMcpDeleteConfirm(null)}>
            <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
              <div className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <div className="p-3 bg-semantic-error-light rounded-full">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-semantic-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-surface-900">Delete MCP Server</h3>
                    <p className="text-sm text-surface-500">This action cannot be undone</p>
                  </div>
                </div>
                <p className="text-surface-700 mb-6">
                  Are you sure you want to delete <span className="font-semibold text-primary-600">{mcpDeleteConfirm}</span>?
                </p>
                <div className="flex justify-end gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setMcpDeleteConfirm(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => deleteMcpServer(mcpDeleteConfirm)}
                    isLoading={saving}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SkillsPage;
