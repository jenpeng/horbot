import React, { Suspense, useState, useEffect, useMemo, useRef } from 'react';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button, IconButton } from '../components/ui/Button';
import Tabs from '../components/ui/Tabs';
import { PageErrorState, PageLoadingState } from '../components/state';
import { useI18n } from '../contexts/I18nContext';
import skillsService from '../services/skills';
import type { Skill, SkillDetail, MCPServerConfig, SkillInstallOption, SkillCompatibility, SkillGraph, SkillGraphEdge, SkillGraphNode } from '../types';
import { lazyWithReload } from '../utils/lazyWithReload';

const MarkdownRenderer = lazyWithReload('MarkdownRenderer', () => import('../components/MarkdownRenderer'));

type PositionedGraphNode = SkillGraphNode & {
  x: number;
  y: number;
};

const truncateGraphLabel = (value: string, maxLength = 24) => {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1)}…`;
};

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

const formatInstallCommand = (option: SkillInstallOption): string | null => {
  if (option.command) {
    return option.command;
  }
  if (option.kind === 'brew' && option.formula) {
    return `brew install ${option.formula}`;
  }
  if (option.kind === 'apt' && option.package) {
    return `sudo apt-get install -y ${option.package}`;
  }
  return null;
};

const getCompatibilityBadge = (
  compatibility: SkillCompatibility | undefined,
  t: (key: string, values?: Record<string, string | number>) => string,
) => {
  if (!compatibility || compatibility.status === 'compatible') {
    return null;
  }
  if (compatibility.status === 'warning') {
    return { label: t('skills.compatibility.needsSetup'), className: 'bg-accent-amber/15 text-accent-amber' };
  }
  return { label: t('skills.compatibility.incompatible'), className: 'bg-semantic-error-light text-semantic-error' };
};

const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

const SkillsPage: React.FC = () => {
  const { t } = useI18n();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [mcpServers, setMcpServers] = useState<Record<string, MCPServerConfig>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'skills' | 'graph' | 'mcp'>('skills');
  const [skillsView, setSkillsView] = useState<'all' | 'system' | 'custom'>('custom');
  const [skillGraph, setSkillGraph] = useState<SkillGraph | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphLoadedOnce, setGraphLoadedOnce] = useState(false);
  const [showGraphPath, setShowGraphPath] = useState(false);
  const [selectedGraphSkill, setSelectedGraphSkill] = useState<string | null>(null);
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
  const [expandedMissingDetails, setExpandedMissingDetails] = useState<Set<string>>(new Set());
  const [hoveredMissingDetails, setHoveredMissingDetails] = useState<string | null>(null);
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
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const markdownPreviewFallback = useMemo(() => (
    <div className="rounded-xl border border-surface-200 bg-white/70 px-4 py-6 text-sm text-surface-500">
      {t('skills.markdownPreviewLoading')}
    </div>
  ), [t]);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [skillsData, mcpData, graphData] = await Promise.all([
        skillsService.getSkills(),
        skillsService.getMcpServers(),
        skillsService.getSkillGraph().catch(() => null),
      ]);
      setSkills(skillsData || []);
      setMcpServers(mcpData || {});
      if (graphData) {
        setSkillGraph(graphData);
        setGraphLoadedOnce(true);
        setSelectedGraphSkill((current) => current ?? graphData.nodes.find((node) => node.kind === 'skill')?.id ?? null);
      }
      setError(null);
    } catch (err) {
      setError(t('skills.notification.fetchFailed'));
      console.error('Error fetching data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, []);

  useEffect(() => {
    if (activeTab !== 'graph' || graphLoadedOnce || graphLoading) {
      return;
    }
    void fetchSkillGraph();
  }, [activeTab, graphLoadedOnce, graphLoading]);

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 3000);
  };

  const fetchSkillGraph = async () => {
    setGraphLoading(true);
    try {
      const graph = await skillsService.getSkillGraph();
      setSkillGraph(graph);
      setSelectedGraphSkill((current) => current ?? graph.nodes.find((node) => node.kind === 'skill')?.id ?? null);
    } catch (err: any) {
      showNotification('error', err.message || t('skills.notification.graphLoadFailed'));
    } finally {
      setGraphLoadedOnce(true);
      setGraphLoading(false);
    }
  };

  const systemSkills = useMemo(
    () => skills.filter((skill) => (skill.source_group ?? (skill.source === 'builtin' ? 'system' : 'custom')) === 'system'),
    [skills],
  );
  const customSkills = useMemo(
    () => skills.filter((skill) => (skill.source_group ?? (skill.source === 'builtin' ? 'system' : 'custom')) === 'custom'),
    [skills],
  );
  const scopedSkills = useMemo(() => {
    if (skillsView === 'system') return systemSkills;
    if (skillsView === 'custom') return customSkills;
    return skills;
  }, [customSkills, skills, skillsView, systemSkills]);
  const filteredSkills = useMemo(() => {
    if (!searchQuery) return scopedSkills;
    const query = searchQuery.toLowerCase();
    return scopedSkills.filter(skill =>
      skill.name.toLowerCase().includes(query) ||
      skill.description.toLowerCase().includes(query)
    );
  }, [scopedSkills, searchQuery]);
  const visibleSelectedCount = useMemo(
    () => filteredSkills.filter((skill) => selectedSkills.has(skill.name)).length,
    [filteredSkills, selectedSkills],
  );
  const searchPlaceholder = useMemo(() => {
    if (skillsView === 'system') return t('skills.searchPlaceholderSystem');
    if (skillsView === 'custom') return t('skills.searchPlaceholderCustom');
    return t('skills.searchPlaceholderAll');
  }, [skillsView, t]);
  const skillViewTabs = useMemo(
    () => [
      { id: 'custom', label: t('skills.viewCustom', { count: customSkills.length }) },
      { id: 'system', label: t('skills.viewSystem', { count: systemSkills.length }) },
      { id: 'all', label: t('skills.viewAll', { count: skills.length }) },
    ],
    [customSkills.length, skills.length, systemSkills.length, t],
  );
  const graphStats = useMemo(() => {
    const graph = skillGraph;
    if (!graph) {
      return {
        skillNodes: 0,
        referenceNodes: 0,
        similarEdges: 0,
        referenceEdges: 0,
      };
    }
    return {
      skillNodes: graph.nodes.filter((node) => node.kind === 'skill').length,
      referenceNodes: graph.nodes.filter((node) => node.kind === 'reference').length,
      similarEdges: graph.edges.filter((edge) => edge.type === 'similar_to').length,
      referenceEdges: graph.edges.filter((edge) => edge.type === 'has_reference').length,
    };
  }, [skillGraph]);
  const graphVisualization = useMemo(() => {
    const graph = skillGraph;
    if (!graph) {
      return {
        nodes: [] as PositionedGraphNode[],
        edges: [] as SkillGraphEdge[],
        selectedNode: null as SkillGraphNode | null,
        focusSkills: [] as SkillGraphNode[],
        referenceNodes: [] as SkillGraphNode[],
        relatedNodes: [] as SkillGraphNode[],
      };
    }

    const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
    const focusSkills = graph.nodes
      .filter((node) => node.kind === 'skill')
      .sort((left, right) => right.reference_count - left.reference_count || left.name.localeCompare(right.name))
      .slice(0, 18);
    const maybeSelected = nodeById.get(selectedGraphSkill || '');
    const selectedNode = maybeSelected?.kind === 'skill' ? maybeSelected : focusSkills[0] ?? null;

    if (!selectedNode) {
      return {
        nodes: [] as PositionedGraphNode[],
        edges: [] as SkillGraphEdge[],
        selectedNode: null as SkillGraphNode | null,
        focusSkills,
        referenceNodes: [] as SkillGraphNode[],
        relatedNodes: [] as SkillGraphNode[],
      };
    }

    const referenceNodes = graph.edges
      .filter((edge) => edge.type === 'has_reference' && edge.source === selectedNode.id)
      .map((edge) => nodeById.get(edge.target))
      .filter((node): node is SkillGraphNode => Boolean(node && node.kind === 'reference'))
      .slice(0, 8);

    const relatedNodes = graph.edges
      .filter((edge) => edge.type !== 'has_reference' && (edge.source === selectedNode.id || edge.target === selectedNode.id))
      .sort((left, right) => right.confidence - left.confidence)
      .map((edge) => nodeById.get(edge.source === selectedNode.id ? edge.target : edge.source))
      .filter((node): node is SkillGraphNode => Boolean(node && node.kind === 'skill' && node.id !== selectedNode.id));
    const dedupedRelatedNodes = Array.from(new Map(relatedNodes.map((node) => [node.id, node])).values()).slice(0, 6);

    const positionColumn = (nodes: SkillGraphNode[], x: number, top = 70, height = 280): PositionedGraphNode[] => {
      const gap = nodes.length > 1 ? height / (nodes.length - 1) : 0;
      return nodes.map((node, index) => ({
        ...node,
        x,
        y: nodes.length > 1 ? top + gap * index : 210,
      }));
    };

    const nodes = [
      ...positionColumn(dedupedRelatedNodes, 170, 85, 250),
      { ...selectedNode, x: 450, y: 210 },
      ...positionColumn(referenceNodes, 730, 70, 280),
    ];
    const visibleIds = new Set(nodes.map((node) => node.id));
    const edges = graph.edges
      .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      .filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
      .slice(0, 18);

    return { nodes, edges, selectedNode, focusSkills, referenceNodes, relatedNodes: dedupedRelatedNodes };
  }, [selectedGraphSkill, skillGraph]);

  const getSkillOriginLabel = (skill: Skill) => {
    if (skill.source === 'builtin' || skill.source_origin_kind === 'builtin') {
      return t('skills.badge.system');
    }
    if (skill.source_origin_kind === 'agent' && skill.source_origin_agent_id) {
      return t('skills.badge.agentSource', { agentId: skill.source_origin_agent_id });
    }
    return t('skills.badge.manual');
  };

  const getSkillPathHint = (skill: SkillDetail) => {
    if (skill.source === 'builtin' || skill.source_origin_kind === 'builtin') {
      return t('skills.detail.pathHintSystem');
    }
    if (skill.source_origin_kind === 'agent' && skill.source_origin_agent_id) {
      return t('skills.detail.pathHintAgent', { agentId: skill.source_origin_agent_id });
    }
    return t('skills.detail.pathHintCustom');
  };

  const renderSkillCards = (skillsToRender: Skill[]) => (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {skillsToRender.map((skill) => (
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
                title={skill.enabled ? t('skills.action.disable') : t('skills.action.enable')}
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
                  <button
                    type="button"
                    className="inline-flex items-center gap-1.5 rounded-md bg-accent-red/10 px-3 py-1.5 text-xs font-semibold leading-tight text-accent-red transition-colors hover:bg-accent-red/15"
                    aria-expanded={expandedMissingDetails.has(skill.name)}
                    aria-controls={`skill-missing-details-${skill.name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleMissingDetails(skill.name);
                    }}
                    onMouseEnter={() => setHoveredMissingDetails(skill.name)}
                    onMouseLeave={() => setHoveredMissingDetails((current) => (
                      current === skill.name ? null : current
                    ))}
                    data-testid={`skill-missing-toggle-${skill.name}`}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    {t('skills.badge.missing')}
                  </button>
                )}
                {getCompatibilityBadge(skill.compatibility, t) && (
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getCompatibilityBadge(skill.compatibility, t)?.className}`}>
                    {getCompatibilityBadge(skill.compatibility, t)?.label}
                  </span>
                )}
                {skill.always && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-accent-purple/10 text-accent-purple">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {t('skills.badge.always')}
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
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                  skill.source === 'builtin'
                    ? 'bg-accent-indigo/10 text-accent-indigo'
                    : 'bg-primary-100 text-primary-700'
                }`}>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  {skill.source === 'builtin' ? t('skills.badge.system') : t('skills.badge.custom')}
                </span>
                {skill.source !== 'builtin' && (
                  <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-surface-100 text-surface-700">
                    {getSkillOriginLabel(skill)}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); void handleExportSkill(skill.name); }}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-surface-200 bg-white text-surface-600 shadow-sm transition-colors hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
                  title={t('skills.action.export')}
                  aria-label={t('skills.action.export')}
                  disabled={saving}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v10m0 0l-4-4m4 4l4-4M4 20h16" />
                  </svg>
                </button>
                {skill.source === 'user' && (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); void handlePromoteSkill(skill.name); }}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-accent-indigo/25 bg-accent-indigo/10 text-accent-indigo shadow-sm transition-colors hover:bg-accent-indigo/15 disabled:cursor-not-allowed disabled:opacity-50"
                    title={t('skills.action.promoteBuiltin')}
                    aria-label={t('skills.action.promoteBuiltin')}
                    disabled={saving}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                  </button>
                )}
                {skill.source === 'user' && (
                  <div className="flex gap-1 opacity-70 transition-opacity group-hover:opacity-100">
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
            </div>

            {((skill.missing_requirements && skill.missing_requirements.length > 0) || (skill.install && skill.install.length > 0 && !skill.available)) &&
              (expandedMissingDetails.has(skill.name) || hoveredMissingDetails === skill.name) && (
              <div
                id={`skill-missing-details-${skill.name}`}
                className="mt-3 bg-semantic-error-light border border-semantic-error/20 rounded-lg p-3"
                onMouseEnter={() => setHoveredMissingDetails(skill.name)}
                onMouseLeave={() => setHoveredMissingDetails((current) => (
                  current === skill.name ? null : current
                ))}
              >
                <div className="space-y-2 text-xs text-semantic-error">
                  {skill.missing_requirements && skill.missing_requirements.length > 0 && (
                    <p className="flex items-start gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span><strong>{t('skills.missingRequirements')}</strong> {skill.missing_requirements.join(', ')}</span>
                    </p>
                  )}
                  {skill.install && skill.install.length > 0 && !skill.available && (
                    <div className="pl-6 space-y-2">
                      {skill.install.map((option, index) => {
                        const command = formatInstallCommand(option);
                        return (
                          <div key={`${option.id || option.kind || 'install'}-${index}`} className="space-y-1">
                            <p className="font-medium text-semantic-error">
                              {option.label || t('skills.installDependency')}
                            </p>
                            {command && (
                              <code className="block rounded bg-white/80 px-2 py-1 font-mono text-[11px] text-surface-700 break-all">
                                {command}
                              </code>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}
            {skill.compatibility && (skill.compatibility.issues.length > 0 || skill.compatibility.warnings.length > 0) && (
              <div className="mt-3 rounded-lg border border-surface-200 bg-surface-50 p-3 text-xs text-surface-700 space-y-2">
                {skill.compatibility.issues.length > 0 && (
                  <p><strong>{t('skills.compatibilityIssues')}</strong> {skill.compatibility.issues.join('; ')}</p>
                )}
                {skill.compatibility.warnings.length > 0 && (
                  <p><strong>{t('skills.compatibilityWarnings')}</strong> {skill.compatibility.warnings.join('; ')}</p>
                )}
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );

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
      content: '---\nname: my-skill\ndescription: Describe when this skill should be used.\n---\n\n# My Skill\n\n## Instructions\n\n- Step 1\n- Step 2\n',
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
      showNotification('error', t('skills.notification.loadForEditingFailed'));
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
      showNotification('error', t('skills.notification.requiredNameContent'));
      return;
    }

    setSaving(true);
    try {
      if (editor.mode === 'create') {
        await skillsService.createSkill({
          name: editor.skillName.trim(),
          content: editor.content
        });
        showNotification('success', t('skills.notification.created', { name: editor.skillName }));
      } else {
        await skillsService.updateSkill(editor.skillName, {
          content: editor.content
        });
        showNotification('success', t('skills.notification.updated', { name: editor.skillName }));
      }
      closeEditor();
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || t('skills.notification.saveFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (skillName: string) => {
    setSaving(true);
    try {
      await skillsService.deleteSkill(skillName);
      showNotification('success', t('skills.notification.deleted', { name: skillName }));
      setDeleteConfirm(null);
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || t('skills.notification.deleteFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (skillName: string, _currentEnabled: boolean) => {
    try {
      const newEnabled = await skillsService.toggleSkill(skillName);
      showNotification('success', t('skills.notification.toggled', {
        name: skillName,
        status: newEnabled ? t('tasks.status.enabled') : t('tasks.status.disabled'),
      }));
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || t('skills.notification.toggleFailed');
      showNotification('error', message);
    }
  };

  const handlePromoteSkill = async (skillName: string) => {
    setSaving(true);
    try {
      await skillsService.promoteSkill(skillName);
      showNotification('success', t('skills.notification.promotedBuiltin', { name: skillName }));
      await fetchData();
    } catch (err: any) {
      const message =
        err.message ||
        err.response?.data?.detail ||
        t('skills.notification.promoteBuiltinFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleExportSkill = async (skillName: string) => {
    setSaving(true);
    try {
      const blob = await skillsService.exportSkill(skillName);
      downloadBlob(blob, `${skillName}.skill`);
      showNotification('success', t('skills.notification.exported', { name: skillName }));
    } catch (err: any) {
      const message =
        err.message ||
        err.response?.data?.detail ||
        t('skills.notification.exportFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleImportClick = () => {
    importInputRef.current?.click();
  };

  const handleImportSkill = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }

    setSaving(true);
    try {
      const result = await skillsService.importSkill(file);
      const statusLabel =
        result.compatibility.status === 'compatible'
          ? t('skills.importStatus.compatible')
          : result.compatibility.status === 'warning'
            ? t('skills.importStatus.warning')
            : t('skills.importStatus.incompatible');
      showNotification('success', t('skills.notification.imported', { name: result.name, status: statusLabel }));
      await fetchData();
    } catch (err: any) {
      const message = err.message || err.response?.data?.detail || t('skills.notification.importFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleConsolidateGeneratedSkills = async () => {
    setSaving(true);
    try {
      const result = await skillsService.consolidateGeneratedSkills();
      showNotification(
        'success',
        result.merged_skill_count > 0
          ? t('skills.notification.consolidatedGenerated', {
              merged: result.merged_skill_count,
              families: result.updated_families.length,
            })
          : t('skills.notification.noGeneratedConsolidationNeeded'),
      );
      await fetchData();
    } catch (err: any) {
      const message =
        err.message ||
        err.response?.data?.detail ||
        t('skills.notification.consolidateGeneratedFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const handleRebuildSkillGraph = async () => {
    setGraphLoading(true);
    setSaving(true);
    try {
      const graph = await skillsService.rebuildSkillGraph();
      setSkillGraph(graph);
      setGraphLoadedOnce(true);
      setSelectedGraphSkill(graph.nodes.find((node) => node.kind === 'skill')?.id ?? null);
      showNotification('success', t('skills.notification.graphRebuilt', {
        nodes: graph.node_count,
        edges: graph.edge_count,
      }));
    } catch (err: any) {
      const message =
        err.message ||
        err.response?.data?.detail ||
        t('skills.notification.graphRebuildFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
      setGraphLoading(false);
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
      showNotification('success', t('skills.notification.batchToggled', {
        count: skillsToToggle.length,
        status: enable ? t('tasks.status.enabled') : t('tasks.status.disabled'),
      }));
      setSelectedSkills(new Set());
      fetchData();
    } catch (err: any) {
      showNotification('error', t('skills.notification.batchToggleFailed'));
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

  const toggleMissingDetails = (skillName: string) => {
    setExpandedMissingDetails((current) => {
      const next = new Set(current);
      if (next.has(skillName)) {
        next.delete(skillName);
      } else {
        next.add(skillName);
      }
      return next;
    });
  };

  const selectAllSkills = () => {
    const visibleSkillNames = filteredSkills.map((skill) => skill.name);
    const nextSelected = new Set(selectedSkills);
    if (visibleSelectedCount === filteredSkills.length) {
      visibleSkillNames.forEach((skillName) => nextSelected.delete(skillName));
    } else {
      visibleSkillNames.forEach((skillName) => nextSelected.add(skillName));
    }
    setSelectedSkills(nextSelected);
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
      showNotification('error', t('skills.notification.serverNameRequired'));
      return;
    }
    if (!mcpEditor.command.trim() && !mcpEditor.url.trim()) {
      showNotification('error', t('skills.notification.commandOrUrlRequired'));
      return;
    }

    setSaving(true);
    try {
      let env: Record<string, string> | undefined;
      if (mcpEditor.env.trim()) {
        try {
          env = JSON.parse(mcpEditor.env);
        } catch {
          showNotification('error', t('skills.notification.invalidEnvJson'));
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
        showNotification('success', t('skills.notification.mcpCreated', { name: mcpEditor.name }));
      } else {
        await skillsService.updateMcpServer(mcpEditor.name.trim(), config);
        showNotification('success', t('skills.notification.mcpUpdated', { name: mcpEditor.name }));
      }
      closeMcpEditor();
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || t('skills.notification.mcpSaveFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  const deleteMcpServer = async (name: string) => {
    setSaving(true);
    try {
      await skillsService.deleteMcpServer(name);
      showNotification('success', t('skills.notification.mcpDeleted', { name }));
      setMcpDeleteConfirm(null);
      fetchData();
    } catch (err: any) {
      const message = err.response?.data?.detail || t('skills.notification.mcpDeleteFailed');
      showNotification('error', message);
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return <PageLoadingState metricCount={2} showTabs />;
  }

  if (error && skills.length === 0 && Object.keys(mcpServers).length === 0) {
    return (
      <PageErrorState
        error={error}
        onRetry={() => { void fetchData(); }}
        title={t('skills.loadErrorTitle')}
      />
    );
  }

  const tabs = [
    { id: 'skills', label: t('skills.tabSkills', { count: skills.length }), icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    )},
    { id: 'graph', label: t('skills.tabGraph', { count: skillGraph?.edge_count ?? 0 }), icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M17 7h.01M12 17h.01M7.05 7.05l4.9 9.9m4.9-9.9l-4.9 9.9M7 7h10" />
      </svg>
    )},
    { id: 'mcp', label: t('skills.tabMcpServers', { count: Object.keys(mcpServers).length }), icon: (
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
              <h2 className="text-3xl font-bold text-surface-900">{t('skills.pageTitle')}</h2>
              <p className="text-sm text-surface-600 mt-1">{t('skills.pageSubtitle')}</p>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => { void fetchData(); }}
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
                {t('common.refresh')}
              </Button>
              {activeTab === 'skills' && (
                <>
                  <input
                    ref={importInputRef}
                    type="file"
                    accept=".skill,.zip"
                    className="hidden"
                    onChange={handleImportSkill}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleImportClick}
                    disabled={saving}
                    leftIcon={
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1M12 4v12m0-12l-4 4m4-4l4 4" />
                      </svg>
                    }
                  >
                    {t('skills.importSkill')}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => { void handleConsolidateGeneratedSkills(); }}
                    disabled={saving}
                    leftIcon={
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7h8m-8 5h16m-16 5h10" />
                      </svg>
                    }
                  >
                    {t('skills.consolidateGenerated')}
                  </Button>
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
                    {t('skills.newSkill')}
                  </Button>
                </>
              )}
              {activeTab === 'graph' && (
                <>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => { void fetchSkillGraph(); }}
                    disabled={graphLoading}
                    leftIcon={
                      <svg xmlns="http://www.w3.org/2000/svg" className={`h-4 w-4 ${graphLoading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    }
                  >
                    {t('skills.graph.refresh')}
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => { void handleRebuildSkillGraph(); }}
                    disabled={saving || graphLoading}
                    leftIcon={
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12h6l3-8 3 16 3-8h3" />
                      </svg>
                    }
                  >
                    {t('skills.graph.rebuild')}
                  </Button>
                </>
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
                  {t('skills.addMcpServer')}
                </Button>
              )}
            </div>
          </div>
        </div>

        <Tabs
          tabs={tabs}
          activeTab={activeTab}
          onChange={(id) => setActiveTab(id as 'skills' | 'graph' | 'mcp')}
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
              <div className="space-y-4 p-4 bg-white rounded-xl border border-surface-200 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <Tabs
                    tabs={skillViewTabs}
                    activeTab={skillsView}
                    onChange={(id) => setSkillsView(id as 'all' | 'system' | 'custom')}
                    variant="pills"
                    className="flex-wrap"
                  />
                  <div className="text-sm text-surface-500">
                    {t('skills.resultsCount', { count: filteredSkills.length, total: scopedSkills.length })}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="relative flex-1 max-w-md">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder={searchPlaceholder}
                    className="w-full pl-10 pr-4 py-2 bg-surface-50 border border-surface-200 rounded-lg text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-surface-500 transition-colors hover:text-surface-800"
                    >
                      {t('skills.clearSearch')}
                    </button>
                  )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={selectAllSkills}
                      className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                    >
                      {visibleSelectedCount === filteredSkills.length ? t('skills.deselectAll') : t('skills.selectAll')}
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
                          {t('skills.batchEnable', { count: selectedSkills.size })}
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleBatchToggle(false)}
                          disabled={saving}
                        >
                          {t('skills.batchDisable', { count: selectedSkills.size })}
                        </Button>
                      </>
                    )}
                  </div>
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
                <p className="text-surface-600 mb-4 font-medium">{t('skills.emptyTitle')}</p>
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
                  {t('skills.emptyAction')}
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-semibold text-surface-900">
                    {skillsView === 'system'
                      ? t('skills.section.system', { count: systemSkills.length })
                      : skillsView === 'custom'
                        ? t('skills.section.custom', { count: customSkills.length })
                        : t('skills.section.all', { count: skills.length })}
                  </h3>
                  <p className="text-sm text-surface-600">
                    {skillsView === 'system'
                      ? t('skills.section.systemSubtitle')
                      : skillsView === 'custom'
                        ? t('skills.section.customSubtitle')
                        : t('skills.section.allSubtitle')}
                  </p>
                </div>
                {renderSkillCards(filteredSkills)}
              </div>
            )}
          </div>
        )}

        {activeTab === 'graph' && (
          <div className="space-y-5">
            <Card padding="md" className="overflow-hidden">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-surface-900">{t('skills.graph.title')}</h3>
                  <p className="text-sm text-surface-600 mt-1">
                    {skillGraph?.persisted
                      ? t('skills.graph.persistedHint')
                      : t('skills.graph.ephemeralHint')}
                  </p>
                  {skillGraph?.path && (
                    <div className="mt-2">
                      <button
                        type="button"
                        className="text-xs font-semibold text-surface-500 underline decoration-surface-300 underline-offset-4 transition-colors hover:text-surface-800"
                        onClick={() => setShowGraphPath((value) => !value)}
                      >
                        {showGraphPath ? t('skills.graph.hidePath') : t('skills.graph.showPath')}
                      </button>
                      {showGraphPath && (
                        <p className="mt-2 rounded-lg bg-surface-50 px-3 py-2 text-xs text-surface-500 font-mono break-all">
                          {skillGraph.path}
                        </p>
                      )}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-center">
                    <div className="text-xl font-bold text-surface-900">{graphStats.skillNodes}</div>
                    <div className="text-xs text-surface-500">{t('skills.graph.skillNodes')}</div>
                  </div>
                  <div className="rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-center">
                    <div className="text-xl font-bold text-surface-900">{graphStats.referenceNodes}</div>
                    <div className="text-xs text-surface-500">{t('skills.graph.referenceNodes')}</div>
                  </div>
                  <div className="rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-center">
                    <div className="text-xl font-bold text-surface-900">{graphStats.referenceEdges}</div>
                    <div className="text-xs text-surface-500">{t('skills.graph.referenceEdges')}</div>
                  </div>
                  <div className="rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-center">
                    <div className="text-xl font-bold text-surface-900">{graphStats.similarEdges}</div>
                    <div className="text-xs text-surface-500">{t('skills.graph.similarEdges')}</div>
                  </div>
                </div>
              </div>
            </Card>

            {graphLoading && !skillGraph ? (
              <div className="flex h-56 items-center justify-center rounded-2xl border border-surface-200 bg-white text-sm text-surface-500">
                {t('skills.graph.loading')}
              </div>
            ) : !skillGraph || skillGraph.nodes.length === 0 ? (
              <div className="flex h-56 flex-col items-center justify-center rounded-2xl border border-surface-200 bg-white text-center">
                <p className="font-medium text-surface-700">{t('skills.graph.emptyTitle')}</p>
                <p className="mt-1 text-sm text-surface-500">{t('skills.graph.emptySubtitle')}</p>
                <Button
                  variant="primary"
                  size="sm"
                  className="mt-4"
                  onClick={() => { void handleRebuildSkillGraph(); }}
                  disabled={saving || graphLoading}
                >
                  {t('skills.graph.rebuild')}
                </Button>
              </div>
            ) : (
              <div className="space-y-5">
                <Card padding="md" className="overflow-hidden">
                  <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <h4 className="font-semibold text-surface-900">{t('skills.graph.visualTitle')}</h4>
                      <p className="text-xs text-surface-500">{t('skills.graph.visualSubtitle')}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-surface-500">
                      <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-primary-500" />{t('skills.graph.legend.skill')}</span>
                      <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-accent-emerald" />{t('skills.graph.legend.reference')}</span>
                      <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 rounded-full bg-primary-300" />{t('skills.graph.legend.referenceEdge')}</span>
                      <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-5 rounded-full bg-accent-indigo/70" />{t('skills.graph.legend.relatedEdge')}</span>
                    </div>
                  </div>
                  <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)_260px]">
                    <div className="rounded-2xl border border-surface-200 bg-surface-50/80 p-3">
                      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-surface-500">
                        {t('skills.graph.focusList')}
                      </div>
                      <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
                        {graphVisualization.focusSkills.map((node) => (
                          <button
                            key={node.id}
                            type="button"
                            onClick={() => setSelectedGraphSkill(node.id)}
                            className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
                              graphVisualization.selectedNode?.id === node.id
                                ? 'border-primary-200 bg-white text-primary-700 shadow-sm'
                                : 'border-transparent bg-transparent text-surface-600 hover:bg-white hover:text-surface-900'
                            }`}
                          >
                            <div className="truncate text-sm font-semibold">{node.name}</div>
                            <div className="mt-1 text-xs text-surface-500">
                              {t('skills.graph.referencesCount', { count: node.reference_count })}
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="relative overflow-hidden rounded-2xl border border-surface-200 bg-[radial-gradient(circle_at_50%_50%,rgba(59,130,246,0.12),transparent_34%),linear-gradient(135deg,rgba(248,250,252,1),rgba(255,255,255,1))]">
                      <svg
                        role="img"
                        aria-label={t('skills.graph.visualTitle')}
                        viewBox="0 0 900 420"
                        className="h-[390px] w-full"
                      >
                        <defs>
                          <marker id="skillGraphArrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                            <path d="M0,0 L0,6 L8,3 z" fill="#93a4bd" />
                          </marker>
                          <filter id="skillGraphShadow" x="-20%" y="-20%" width="140%" height="140%">
                            <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#0f172a" floodOpacity="0.10" />
                          </filter>
                        </defs>
                        {graphVisualization.edges.map((edge) => {
                          const source = graphVisualization.nodes.find((node) => node.id === edge.source);
                          const target = graphVisualization.nodes.find((node) => node.id === edge.target);
                          if (!source || !target) {
                            return null;
                          }
                          const stroke = edge.type === 'has_reference' ? '#93c5fd' : '#818cf8';
                          const dash = edge.type === 'has_reference' ? undefined : '7 7';
                          const midX = (source.x + target.x) / 2;
                          return (
                            <path
                              key={edge.id}
                              d={`M ${source.x + 74} ${source.y} C ${midX} ${source.y}, ${midX} ${target.y}, ${target.x - 74} ${target.y}`}
                              fill="none"
                              stroke={stroke}
                              strokeWidth={Math.max(1.5, edge.confidence * 3)}
                              strokeDasharray={dash}
                              opacity="0.72"
                              markerEnd="url(#skillGraphArrow)"
                            />
                          );
                        })}
                        {graphVisualization.nodes.map((node) => {
                          const isReference = node.kind === 'reference';
                          const isSelected = graphVisualization.selectedNode?.id === node.id;
                          return (
                            <g
                              key={node.id}
                              transform={`translate(${node.x}, ${node.y})`}
                              filter="url(#skillGraphShadow)"
                              className={isReference ? '' : 'cursor-pointer'}
                              onClick={() => {
                                if (!isReference) {
                                  setSelectedGraphSkill(node.id);
                                }
                              }}
                            >
                              <rect
                                x={isSelected ? '-104' : '-86'}
                                y={isSelected ? '-34' : '-28'}
                                width={isSelected ? '208' : '172'}
                                height={isSelected ? '68' : '56'}
                                rx="18"
                                className={
                                  isReference
                                    ? 'fill-emerald-50 stroke-emerald-200'
                                    : isSelected
                                      ? 'fill-primary-600 stroke-primary-700'
                                      : 'fill-white stroke-primary-200'
                                }
                                strokeWidth="1.5"
                              />
                              <circle
                                cx={isSelected ? '-78' : '-62'}
                                cy="0"
                                r="10"
                                className={isReference ? 'fill-accent-emerald' : isSelected ? 'fill-white' : 'fill-primary-500'}
                              />
                              <text x={isSelected ? '-60' : '-44'} y="-4" className={`${isSelected ? 'fill-white' : 'fill-surface-900'} text-[12px] font-semibold`}>
                                {truncateGraphLabel(node.name, isSelected ? 26 : 22)}
                              </text>
                              <text x={isSelected ? '-60' : '-44'} y="14" className={`${isSelected ? 'fill-primary-100' : 'fill-surface-500'} text-[10px]`}>
                                {isReference ? t('skills.graph.legend.reference') : isSelected ? t('skills.graph.focusNode') : t('skills.graph.legend.skill')}
                              </text>
                            </g>
                          );
                        })}
                      </svg>
                    </div>
                    <div className="rounded-2xl border border-surface-200 bg-surface-50/80 p-4">
                      <div className="text-xs font-semibold uppercase tracking-wide text-surface-500">
                        {t('skills.graph.focusDetail')}
                      </div>
                      <div className="mt-2 break-words text-sm font-semibold text-surface-900">
                        {graphVisualization.selectedNode?.name}
                      </div>
                      <p className="mt-2 line-clamp-4 text-sm text-surface-600">
                        {graphVisualization.selectedNode?.description}
                      </p>
                      <div className="mt-4 grid grid-cols-2 gap-2">
                        <div className="rounded-xl bg-white p-3 text-center ring-1 ring-surface-200">
                          <div className="text-lg font-bold text-surface-900">{graphVisualization.referenceNodes.length}</div>
                          <div className="text-xs text-surface-500">{t('skills.graph.legend.reference')}</div>
                        </div>
                        <div className="rounded-xl bg-white p-3 text-center ring-1 ring-surface-200">
                          <div className="text-lg font-bold text-surface-900">{graphVisualization.relatedNodes.length}</div>
                          <div className="text-xs text-surface-500">{t('skills.graph.legend.relatedEdge')}</div>
                        </div>
                      </div>
                      <div className="mt-4 space-y-2">
                        {graphVisualization.relatedNodes.map((node) => (
                          <button
                            key={node.id}
                            type="button"
                            onClick={() => setSelectedGraphSkill(node.id)}
                            className="w-full truncate rounded-lg bg-white px-3 py-2 text-left text-xs font-semibold text-primary-700 ring-1 ring-primary-100 hover:bg-primary-50"
                          >
                            {node.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </Card>

                <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
                <Card padding="md">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-surface-900">{t('skills.graph.nodesTitle')}</h4>
                      <p className="text-xs text-surface-500">{t('skills.graph.nodesSubtitle')}</p>
                    </div>
                    <Badge variant="default" size="sm">{skillGraph.node_count}</Badge>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {skillGraph.nodes.filter((node) => node.kind === 'skill').slice(0, 24).map((node) => (
                      <div key={node.id} className="rounded-xl border border-surface-200 bg-white p-4 transition-colors hover:border-primary-200 hover:bg-primary-50/40">
                        <div className="flex items-start gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-semibold text-surface-900">{node.name}</p>
                            <p className="mt-1 line-clamp-2 text-sm text-surface-600">{node.description}</p>
                          </div>
                          <span className={`shrink-0 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none ring-1 ${
                            node.source_group === 'system'
                              ? 'bg-accent-indigo/10 text-accent-indigo ring-accent-indigo/15'
                              : 'bg-primary-50 text-primary-700 ring-primary-100'
                          }`}>
                            {node.source_group === 'system' ? t('skills.badge.system') : t('skills.badge.custom')}
                          </span>
                        </div>
                        <div className="mt-3 flex items-center gap-2 text-xs text-surface-500">
                          <span>{t('skills.graph.referencesCount', { count: node.reference_count })}</span>
                          {node.origin_agent_id && <span>· Agent {node.origin_agent_id}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card padding="md">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold text-surface-900">{t('skills.graph.edgesTitle')}</h4>
                      <p className="text-xs text-surface-500">{t('skills.graph.edgesSubtitle')}</p>
                    </div>
                    <Badge variant="default" size="sm">{skillGraph.edge_count}</Badge>
                  </div>
                  <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                    {skillGraph.edges.slice(0, 80).map((edge) => (
                      <div key={edge.id} className="rounded-xl border border-surface-200 bg-surface-50 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-primary-700 ring-1 ring-primary-100">
                            {t(`skills.graph.edge.${edge.type}`)}
                          </span>
                          <span className="text-xs font-medium text-surface-500">
                            {Math.round(edge.confidence * 100)}%
                          </span>
                        </div>
                        <div className="mt-2 text-sm font-medium text-surface-800">
                          <span className="break-all">{edge.source}</span>
                          <span className="mx-2 text-surface-400">→</span>
                          <span className="break-all">{edge.target}</span>
                        </div>
                        <p className="mt-2 text-xs text-surface-500">{edge.reason}</p>
                      </div>
                    ))}
                  </div>
                </Card>
                </div>
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
                <p className="text-surface-600 font-medium">{t('skills.mcp.emptyTitle')}</p>
                <p className="text-sm text-surface-500 mt-1">{t('skills.mcp.emptySubtitle')}</p>
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
                          {t('skills.mcp.secretHidden')}
                        </Badge>
                      )}
                    </div>

                    {server.env && Object.keys(server.env).length > 0 && (
                      <div className="pt-3 border-t border-surface-100">
                        <p className="text-xs font-medium text-surface-500 mb-2 flex items-center gap-1">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                          </svg>
                          {t('skills.mcp.environmentVariables')}
                        </p>
                        <div className="space-y-1">
                          {Object.entries(server.env).slice(0, 3).map(([key, value]) => (
                            <div key={key} className="flex justify-between text-xs bg-surface-50 rounded-lg px-3 py-1.5">
                              <span className="text-primary-600 font-mono font-medium">{key}</span>
                              <span className="text-surface-400">{value ? '•••••••••' : t('skills.mcp.emptyValue')}</span>
                            </div>
                          ))}
                          {Object.keys(server.env).length > 3 && (
                            <p className="text-xs text-surface-400 mt-1 text-center">{t('skills.mcp.moreCount', { count: Object.keys(server.env).length - 3 })}</p>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="mt-3 pt-3 border-t border-surface-100 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></div>
                        <span className="text-xs text-surface-500">{t('skills.mcp.active')}</span>
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
                            {t('skills.detail.alwaysActive')}
                          </span>
                        )}
                        <Badge variant={selectedSkill.available ? 'success' : 'error'} size="sm">
                          {selectedSkill.available ? (
                            <>
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              {t('skills.detail.available')}
                            </>
                          ) : (
                            <>
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                              {t('skills.detail.unavailable')}
                            </>
                          )}
                        </Badge>
                        <Badge variant="default" size="sm">
                          {selectedSkill.schema} v{selectedSkill.schema_version ?? 'n/a'}
                        </Badge>
                        {selectedSkill.normalized_from_legacy && (
                          <Badge variant="warning" size="sm">
                            {t('skills.detail.fromSchema', { schema: selectedSkill.source_schema, version: selectedSkill.source_schema_version ?? 'n/a' })}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => { void handleExportSkill(selectedSkill.name); }}
                        disabled={saving}
                      >
                        {t('skills.action.export')}
                      </Button>
                      {selectedSkill.source === 'user' && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => { void handlePromoteSkill(selectedSkill.name); }}
                          disabled={saving}
                        >
                          {t('skills.action.promoteBuiltin')}
                        </Button>
                      )}
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
                </div>
              </div>

              <div className="p-6 overflow-y-auto max-h-[calc(85vh-120px)]">
                <div className="mb-6">
                  <h4 className="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7h18M3 12h18M3 17h18" />
                    </svg>
                    {t('skills.detail.path')}
                  </h4>
                  <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                    <code className="block font-mono text-xs text-surface-700 break-all">
                      {selectedSkill.path}
                    </code>
                    <p className="mt-3 text-xs text-surface-500">
                      {getSkillPathHint(selectedSkill)}
                    </p>
                  </div>
                </div>

                {Object.keys(selectedSkill.metadata).length > 0 && (
                  <div className="mb-6">
                    <h4 className="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      {t('skills.detail.metadata')}
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
                    {t('skills.detail.content')}
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
                        {editor.mode === 'create'
                          ? t('skills.editor.createTitle')
                          : t('skills.editor.editTitle', { name: editor.skillName })}
                      </h3>
                      <p className="text-sm text-surface-500 mt-1">
                        {editor.mode === 'create' ? t('skills.editor.createSubtitle') : t('skills.editor.editSubtitle')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {hasChanges && (
                      <span className="text-xs text-semantic-warning bg-semantic-warning-light px-2 py-1 rounded-full">
                        {t('skills.editor.unsavedChanges')}
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
                      {t('skills.editor.skillName')}
                    </label>
                    <input
                      type="text"
                      value={editor.skillName}
                      onChange={(e) => setEditor({ ...editor, skillName: e.target.value })}
                      placeholder={t('skills.editor.skillNamePlaceholder')}
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-semibold text-surface-700">
                      {t('skills.editor.content')}
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
                        {t('skills.editor.preview')}
                      </button>
                    </div>
                  </div>
                  
                  <div className={`grid ${showPreview ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
                    <div className="relative">
                      <textarea
                        value={editor.content}
                        onChange={(e) => setEditor({ ...editor, content: e.target.value })}
                        placeholder={t('skills.editor.contentPlaceholder')}
                        rows={20}
                        className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 font-mono text-sm placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 resize-none transition-all"
                      />
                    </div>
                    {showPreview && (
                      <div className="bg-surface-50 border border-surface-200 rounded-xl p-4 overflow-y-auto max-h-[500px]">
                        <div className="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-3">{t('skills.editor.previewLabel')}</div>
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
                  {t('skills.editor.markdownSupported')}
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={closeEditor}
                  >
                    {t('common.cancel')}
                  </Button>
                  {hasChanges && editor.mode === 'edit' && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setEditor({ ...editor, content: editor.originalContent })}
                      disabled={saving}
                    >
                      {t('skills.editor.revert')}
                    </Button>
                  )}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={saveSkill}
                    isLoading={saving}
                    disabled={!editor.skillName.trim() || !editor.content.trim()}
                  >
                    {editor.mode === 'create' ? t('skills.editor.createAction') : t('skills.editor.saveChanges')}
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
                    <h3 className="text-lg font-bold text-surface-900">{t('skills.delete.title')}</h3>
                    <p className="text-sm text-surface-500">{t('skills.delete.subtitle')}</p>
                  </div>
                </div>
                <p className="text-surface-700 mb-6">
                  {t('skills.delete.confirm', { name: deleteConfirm })}
                </p>
                <div className="flex justify-end gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setDeleteConfirm(null)}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(deleteConfirm)}
                    isLoading={saving}
                  >
                    {t('common.delete')}
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
                        {mcpEditor.mode === 'create'
                          ? t('skills.mcpEditor.createTitle')
                          : t('skills.mcpEditor.editTitle', { name: mcpEditor.name })}
                      </h3>
                      <p className="text-sm text-surface-500 mt-1">
                        {mcpEditor.mode === 'create' ? t('skills.mcpEditor.createSubtitle') : t('skills.mcpEditor.editSubtitle')}
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
                      {t('skills.mcpEditor.serverName')} <span className="text-semantic-error">*</span>
                    </label>
                    <input
                      type="text"
                      value={mcpEditor.name}
                      onChange={(e) => setMcpEditor({ ...mcpEditor, name: e.target.value })}
                      placeholder={t('skills.mcpEditor.serverNamePlaceholder')}
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                    <p className="text-xs text-surface-500 mt-1">{t('skills.mcpEditor.serverNameHint')}</p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-surface-700 mb-2">
                      {t('skills.mcpEditor.command')}
                    </label>
                    <input
                      type="text"
                      value={mcpEditor.command}
                      onChange={(e) => setMcpEditor({ ...mcpEditor, command: e.target.value })}
                      placeholder={t('skills.mcpEditor.commandPlaceholder')}
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                    <p className="text-xs text-surface-500 mt-1">{t('skills.mcpEditor.commandHint')}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-surface-700 mb-2">
                      {t('skills.mcpEditor.arguments')}
                    </label>
                    <input
                      type="text"
                      value={mcpEditor.args}
                      onChange={(e) => setMcpEditor({ ...mcpEditor, args: e.target.value })}
                      placeholder={t('skills.mcpEditor.argumentsPlaceholder')}
                      className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                    />
                    <p className="text-xs text-surface-500 mt-1">{t('skills.mcpEditor.argumentsHint')}</p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-surface-700 mb-2">
                    {t('skills.mcpEditor.url')}
                  </label>
                  <input
                    type="text"
                    value={mcpEditor.url}
                    onChange={(e) => setMcpEditor({ ...mcpEditor, url: e.target.value })}
                    placeholder={t('skills.mcpEditor.urlPlaceholder')}
                    className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  />
                  <p className="text-xs text-surface-500 mt-1">{t('skills.mcpEditor.urlHint')}</p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-surface-700 mb-2">
                    {t('skills.mcpEditor.env')}
                  </label>
                  <textarea
                    value={mcpEditor.env}
                    onChange={(e) => setMcpEditor({ ...mcpEditor, env: e.target.value })}
                    placeholder={t('skills.mcpEditor.envPlaceholder')}
                    rows={4}
                    className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 font-mono text-sm placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 resize-none transition-all"
                  />
                  <p className="text-xs text-surface-500 mt-1">
                    {t('skills.mcpEditor.envHint')}
                    {mcpEditor.mode === 'edit' && mcpEditor.originalData?.has_secret_values
                      ? t('skills.mcpEditor.envSecretHint')
                      : ''}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-surface-700 mb-2">
                    {t('skills.mcpEditor.toolTimeout')}
                  </label>
                  <input
                    type="number"
                    value={mcpEditor.tool_timeout}
                    onChange={(e) => setMcpEditor({ ...mcpEditor, tool_timeout: parseInt(e.target.value) || 120 })}
                    placeholder={t('skills.mcpEditor.toolTimeoutPlaceholder')}
                    min={10}
                    max={600}
                    className="w-full bg-surface-50 border border-surface-200 rounded-xl px-4 py-3 text-surface-900 placeholder-surface-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  />
                  <p className="text-xs text-surface-500 mt-1">{t('skills.mcpEditor.toolTimeoutHint')}</p>
                </div>

                <div className="bg-primary-50 rounded-xl p-4 border border-primary-100">
                  <h4 className="text-sm font-semibold text-primary-700 mb-2 flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {t('skills.mcpEditor.builtinTitle')}
                  </h4>
                  <div className="space-y-2 text-xs text-primary-600">
                    <p><strong>browser:</strong> python3 -m horbot.mcp.browser.server</p>
                    <p><strong>excel:</strong> python3 -m horbot.mcp.excel.server</p>
                    <p><strong>officecli:</strong> <code>officecli mcp</code> (recommended server names: <code>officecli</code>, <code>office-word</code>, <code>office-excel</code>, <code>office-powerpoint</code>)</p>
                  </div>
                </div>
              </div>

              <div className="p-6 border-t border-surface-200 bg-surface-50 flex justify-between items-center">
                <div className="flex items-center gap-2 text-sm text-surface-500">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {t('skills.mcpEditor.commandOrUrlRequired')}
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={closeMcpEditor}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={saveMcpServer}
                    isLoading={saving}
                    disabled={!mcpEditor.name.trim() || (!mcpEditor.command.trim() && !mcpEditor.url.trim())}
                  >
                    {mcpEditor.mode === 'create' ? t('skills.mcpEditor.addAction') : t('skills.mcpEditor.saveChanges')}
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
                    <h3 className="text-lg font-bold text-surface-900">{t('skills.mcpDelete.title')}</h3>
                    <p className="text-sm text-surface-500">{t('skills.mcpDelete.subtitle')}</p>
                  </div>
                </div>
                <p className="text-surface-700 mb-6">
                  {t('skills.mcpDelete.confirm', { name: mcpDeleteConfirm })}
                </p>
                <div className="flex justify-end gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setMcpDeleteConfirm(null)}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => deleteMcpServer(mcpDeleteConfirm)}
                    isLoading={saving}
                  >
                    {t('common.delete')}
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
