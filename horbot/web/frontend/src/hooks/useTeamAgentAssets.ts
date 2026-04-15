import { useEffect, useRef, useState } from 'react';
import type {
  AgentAssetBundle,
  AgentMemoryStats,
  AgentSkillInfo,
  AgentToolAuditBundle,
  SummaryDrafts,
  SummarySectionKey,
} from '../pages/teams/types';
import {
  buildToolAuditQueryParams,
  createDefaultToolAuditState,
  normalizeToolAuditLimit,
  readToolAuditStateFromUrl,
  TOOL_AUDIT_DEFAULT_LIMIT,
} from '../pages/teams/selection';
import type { TeamsPageAuditUrlState } from '../pages/teams/selection';

const emptyAssetDrafts = () => ({ agents: '', soul: '', user: '' });

const emptySummaryDrafts = (): SummaryDrafts => ({
  identity: '',
  role_focus: '',
  communication_style: '',
  boundaries: '',
  user_preferences: '',
});

const summaryToDrafts = (summary?: AgentAssetBundle['summary']): SummaryDrafts => ({
  identity: (summary?.identity || []).join('\n'),
  role_focus: (summary?.role_focus || []).join('\n'),
  communication_style: (summary?.communication_style || []).join('\n'),
  boundaries: (summary?.boundaries || []).join('\n'),
  user_preferences: (summary?.user_preferences || []).join('\n'),
});

const isJsonContentType = (contentType: string) =>
  contentType.includes('application/json') || contentType.includes('+json');

const readJsonResponse = async <T>(response: Response, resourceLabel: string): Promise<T> => {
  const target = response.url || resourceLabel;
  const contentType = response.headers?.get?.('content-type') || '';

  if (typeof response.text !== 'function') {
    try {
      return await response.json() as T;
    } catch {
      throw new Error(`Invalid JSON response from ${target}`);
    }
  }

  const raw = await response.text();
  const trimmed = raw.trim();
  if (!trimmed) {
    return null as T;
  }

  const looksLikeJson = isJsonContentType(contentType) || trimmed.startsWith('{') || trimmed.startsWith('[');
  if (!looksLikeJson) {
    if (trimmed.startsWith('<')) {
      throw new Error(`API returned HTML instead of JSON for ${target}`);
    }
    throw new Error(`API returned non-JSON response for ${target}`);
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new Error(`Invalid JSON response from ${target}`);
  }
};

const readErrorMessage = async (response: Response, resourceLabel: string, fallback: string) => {
  try {
    const error = await readJsonResponse<{ detail?: string; message?: string } | null>(response, resourceLabel);
    return error?.detail || error?.message || fallback;
  } catch (error: any) {
    return error?.message || fallback;
  }
};

const readOptionalJson = async <T>(responsePromise: Promise<Response>, resourceLabel: string, fallback: T): Promise<T> => {
  try {
    const response = await responsePromise;
    if (!response.ok) {
      return fallback;
    }
    return await readJsonResponse<T>(response, resourceLabel);
  } catch {
    return fallback;
  }
};

interface UseTeamAgentAssetsOptions {
  selectedAgentId: string | null;
  onSaved?: () => Promise<void> | void;
}

export const useTeamAgentAssets = ({
  selectedAgentId,
  onSaved,
}: UseTeamAgentAssetsOptions) => {
  const initialToolAuditStateRef = useRef(readToolAuditStateFromUrl());
  const previousSelectedAgentIdRef = useRef<string | null>(selectedAgentId);
  const [agentAssets, setAgentAssets] = useState<AgentAssetBundle | null>(null);
  const [agentMemoryStats, setAgentMemoryStats] = useState<AgentMemoryStats | null>(null);
  const [agentSkills, setAgentSkills] = useState<AgentSkillInfo[]>([]);
  const [agentToolAudits, setAgentToolAudits] = useState<AgentToolAuditBundle | null>(null);
  const [toolAuditState, setToolAuditState] = useState<TeamsPageAuditUrlState>(initialToolAuditStateRef.current);
  const [toolAuditLoading, setToolAuditLoading] = useState(false);
  const [assetDrafts, setAssetDrafts] = useState(emptyAssetDrafts);
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetLoadedAgentId, setAssetLoadedAgentId] = useState<string | null>(null);
  const [assetSaving, setAssetSaving] = useState<'agents' | 'soul' | 'user' | null>(null);
  const [assetError, setAssetError] = useState('');
  const [assetSuccess, setAssetSuccess] = useState('');
  const [summaryDrafts, setSummaryDrafts] = useState<SummaryDrafts>(emptySummaryDrafts);
  const [summarySaving, setSummarySaving] = useState(false);
  const assetDraftsRef = useRef(emptyAssetDrafts());
  const summaryDraftsRef = useRef<SummaryDrafts>(emptySummaryDrafts());

  const replaceAssetDrafts = (nextDrafts: { agents: string; soul: string; user: string }) => {
    assetDraftsRef.current = nextDrafts;
    setAssetDrafts(nextDrafts);
  };

  const replaceSummaryDrafts = (nextDrafts: SummaryDrafts) => {
    summaryDraftsRef.current = nextDrafts;
    setSummaryDrafts(nextDrafts);
  };

  const resetToolAuditState = () => setToolAuditState(createDefaultToolAuditState());

  const resetAssetState = () => {
    setAgentAssets(null);
    setAgentMemoryStats(null);
    setAgentSkills([]);
    setAgentToolAudits(null);
    resetToolAuditState();
    setToolAuditLoading(false);
    replaceAssetDrafts(emptyAssetDrafts());
    replaceSummaryDrafts(emptySummaryDrafts());
    setAssetLoadedAgentId(null);
    setAssetLoading(false);
  };

  const applyBootstrapBundle = (bootstrapData: AgentAssetBundle, agentId: string) => {
    setAgentAssets(bootstrapData);
    replaceAssetDrafts({
      agents: bootstrapData.files?.agents?.content || '',
      soul: bootstrapData.files?.soul?.content || '',
      user: bootstrapData.files?.user?.content || '',
    });
    replaceSummaryDrafts(summaryToDrafts(bootstrapData.summary));
    setAssetLoadedAgentId(agentId);
  };

  const handleAssetDraftChange = (fileKind: 'agents' | 'soul' | 'user', value: string) => {
    replaceAssetDrafts({
      ...assetDraftsRef.current,
      [fileKind]: value,
    });
  };

  const handleSummaryDraftChange = (key: SummarySectionKey, value: string) => {
    replaceSummaryDrafts({
      ...summaryDraftsRef.current,
      [key]: value,
    });
  };

  const loadToolAudits = async (
    agentId: string,
    nextToolAuditState: TeamsPageAuditUrlState,
    disposedRef?: { current: boolean },
  ) => {
    setToolAuditLoading(true);
    try {
      const params = buildToolAuditQueryParams(agentId, nextToolAuditState);
      const response = await fetch(`/api/memory/tool-audits?${params.toString()}`);
      if (!response.ok) {
        throw new Error(await readErrorMessage(response, '/api/memory/tool-audits', 'Failed to load tool audits'));
      }
      const toolAuditData = await readJsonResponse<AgentToolAuditBundle>(response, '/api/memory/tool-audits');
      if (!disposedRef?.current) {
        setAgentToolAudits(toolAuditData);
      }
    } catch (error: any) {
      if (!disposedRef?.current) {
        setAgentToolAudits(null);
      }
    } finally {
      if (!disposedRef?.current) {
        setToolAuditLoading(false);
      }
    }
  };

  useEffect(() => {
    let disposed = false;
    const disposedRef = { current: false };

    const loadAgentAssets = async () => {
      if (!selectedAgentId) {
        previousSelectedAgentIdRef.current = null;
        resetAssetState();
        return;
      }

      const currentAgentId = selectedAgentId;
      const previousAgentId = previousSelectedAgentIdRef.current;
      previousSelectedAgentIdRef.current = currentAgentId;
      const shouldResetAuditFilters = Boolean(previousAgentId && previousAgentId !== currentAgentId);
      const defaultToolAuditState = createDefaultToolAuditState();
      const effectiveAuditState = shouldResetAuditFilters
        ? defaultToolAuditState
        : toolAuditState;
      setAssetLoading(true);
      setAssetError('');
      setAssetLoadedAgentId(null);
      setAgentAssets(null);
      setAgentMemoryStats(null);
      setAgentSkills([]);
      setAgentToolAudits(null);
      setToolAuditLoading(false);
      if (shouldResetAuditFilters) {
        resetToolAuditState();
      }
      replaceAssetDrafts(emptyAssetDrafts());
      replaceSummaryDrafts(emptySummaryDrafts());

      try {
        const bootstrapRes = await fetch(`/api/agents/${currentAgentId}/bootstrap-files`);

        if (!bootstrapRes.ok) {
          throw new Error(await readErrorMessage(
            bootstrapRes,
            `/api/agents/${currentAgentId}/bootstrap-files`,
            'Failed to load agent bootstrap files',
          ));
        }

        const bootstrapData = await readJsonResponse<AgentAssetBundle>(
          bootstrapRes,
          `/api/agents/${currentAgentId}/bootstrap-files`,
        );
        const [memoryData, skillsData, toolAuditData] = await Promise.all([
          readOptionalJson<AgentMemoryStats | null>(
            fetch(`/api/memory?agent_id=${encodeURIComponent(currentAgentId)}`),
            '/api/memory',
            null,
          ),
          readOptionalJson<{ skills?: AgentSkillInfo[] }>(
            fetch(`/api/skills?agent_id=${encodeURIComponent(currentAgentId)}`),
            '/api/skills',
            { skills: [] },
          ),
          readOptionalJson<AgentToolAuditBundle | null>(
            fetch(`/api/memory/tool-audits?${buildToolAuditQueryParams(currentAgentId, effectiveAuditState).toString()}`),
            '/api/memory/tool-audits',
            null,
          ),
        ]);

        if (disposed) {
          return;
        }

        applyBootstrapBundle(bootstrapData, currentAgentId);
        setAgentMemoryStats(memoryData ? {
          total_entries: memoryData.total_entries || 0,
          total_size_kb: memoryData.total_size_kb || 0,
        } : null);
        setAgentSkills(skillsData.skills || []);
        setAgentToolAudits(toolAuditData);
      } catch (error: any) {
        if (disposed) {
          return;
        }
        setAssetError(error.message || '加载 Agent 资产失败');
      } finally {
        if (!disposed) {
          setAssetLoading(false);
        }
      }
    };

    void loadAgentAssets();

    return () => {
      disposed = true;
      disposedRef.current = true;
    };
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId || assetLoadedAgentId !== selectedAgentId) {
      return;
    }
    const disposedRef = { current: false };
    void loadToolAudits(
      selectedAgentId,
      toolAuditState,
      disposedRef,
    );
    return () => {
      disposedRef.current = true;
    };
  }, [selectedAgentId, assetLoadedAgentId, toolAuditState]);

  const handleToolAuditSessionKeyChange = (value: string) => {
    setToolAuditState((current) => ({
      ...current,
      sessionKey: value,
      limit: TOOL_AUDIT_DEFAULT_LIMIT,
    }));
  };

  const handleToolAuditRiskFilterChange = (value: TeamsPageAuditUrlState['riskKind']) => {
    setToolAuditState((current) => ({
      ...current,
      riskKind: value,
      limit: TOOL_AUDIT_DEFAULT_LIMIT,
    }));
  };

  const handleToolAuditWindowHoursChange = (value: number) => {
    setToolAuditState((current) => ({
      ...current,
      windowHours: value,
      limit: TOOL_AUDIT_DEFAULT_LIMIT,
    }));
  };

  const handleLoadMoreToolAudits = () => {
    setToolAuditState((current) => ({
      ...current,
      limit: normalizeToolAuditLimit(current.limit + TOOL_AUDIT_DEFAULT_LIMIT),
    }));
  };

  const handleSaveAssetFile = async (fileKind: 'agents' | 'soul' | 'user') => {
    if (!selectedAgentId) {
      return;
    }

    try {
      setAssetSaving(fileKind);
      setAssetError('');
      setAssetSuccess('');

      const response = await fetch(`/api/agents/${selectedAgentId}/bootstrap-files/${fileKind}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: assetDraftsRef.current[fileKind] }),
      });

      if (!response.ok) {
        throw new Error(await readErrorMessage(
          response,
          `/api/agents/${selectedAgentId}/bootstrap-files/${fileKind}`,
          'Failed to save bootstrap file',
        ));
      }

      const updated = await fetch(`/api/agents/${selectedAgentId}/bootstrap-files`);
      if (updated.ok) {
        const updatedData = await readJsonResponse<AgentAssetBundle>(
          updated,
          `/api/agents/${selectedAgentId}/bootstrap-files`,
        );
        applyBootstrapBundle(updatedData, selectedAgentId);
      }

      await onSaved?.();
      const savedLabel = fileKind === 'agents' ? 'AGENTS.md' : fileKind === 'soul' ? 'SOUL.md' : 'USER.md';
      setAssetSuccess(`${savedLabel} 已保存`);
    } catch (error: any) {
      setAssetError(error.message || '保存失败');
    } finally {
      setAssetSaving(null);
    }
  };

  const handleSaveSummary = async () => {
    if (!selectedAgentId) {
      return;
    }

    const toItems = (value: string) =>
      value
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean);

    try {
      setSummarySaving(true);
      setAssetError('');
      setAssetSuccess('');

      const response = await fetch(`/api/agents/${selectedAgentId}/bootstrap-summary`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          identity: toItems(summaryDraftsRef.current.identity),
          role_focus: toItems(summaryDraftsRef.current.role_focus),
          communication_style: toItems(summaryDraftsRef.current.communication_style),
          boundaries: toItems(summaryDraftsRef.current.boundaries),
          user_preferences: toItems(summaryDraftsRef.current.user_preferences),
        }),
      });

      if (!response.ok) {
        throw new Error(await readErrorMessage(
          response,
          `/api/agents/${selectedAgentId}/bootstrap-summary`,
          'Failed to save summary',
        ));
      }

      const updatedData = await readJsonResponse<AgentAssetBundle>(
        response,
        `/api/agents/${selectedAgentId}/bootstrap-summary`,
      );
      applyBootstrapBundle(updatedData, selectedAgentId);
      await onSaved?.();
      setAssetSuccess('配置摘要已保存，并已同步写回 SOUL.md / USER.md');
    } catch (error: any) {
      setAssetError(error.message || '保存配置摘要失败');
    } finally {
      setSummarySaving(false);
    }
  };

  return {
    agentAssets,
    agentMemoryStats,
    agentSkills,
    agentToolAudits,
    toolAuditState,
    toolAuditLoading,
    assetDrafts,
    assetLoading,
    assetLoadedAgentId,
    assetSaving,
    assetError,
    assetSuccess,
    summaryDrafts,
    summarySaving,
    handleAssetDraftChange,
    handleSummaryDraftChange,
    handleSaveAssetFile,
    handleSaveSummary,
    setToolAuditState,
    setToolAuditSessionKey: handleToolAuditSessionKeyChange,
    setToolAuditRiskFilter: handleToolAuditRiskFilterChange,
    setToolAuditWindowHours: handleToolAuditWindowHoursChange,
    loadMoreToolAudits: handleLoadMoreToolAudits,
    setAssetError,
    setAssetSuccess,
  };
};
