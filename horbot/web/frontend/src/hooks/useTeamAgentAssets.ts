import { useEffect, useRef, useState } from 'react';
import type {
  AgentAssetBundle,
  AgentMemoryStats,
  AgentSkillInfo,
  SummaryDrafts,
  SummarySectionKey,
} from '../pages/teams/types';

const emptyAssetDrafts = () => ({ soul: '', user: '' });

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

interface UseTeamAgentAssetsOptions {
  selectedAgentId: string | null;
  onSaved?: () => Promise<void> | void;
}

export const useTeamAgentAssets = ({
  selectedAgentId,
  onSaved,
}: UseTeamAgentAssetsOptions) => {
  const [agentAssets, setAgentAssets] = useState<AgentAssetBundle | null>(null);
  const [agentMemoryStats, setAgentMemoryStats] = useState<AgentMemoryStats | null>(null);
  const [agentSkills, setAgentSkills] = useState<AgentSkillInfo[]>([]);
  const [assetDrafts, setAssetDrafts] = useState(emptyAssetDrafts);
  const [assetLoading, setAssetLoading] = useState(false);
  const [assetLoadedAgentId, setAssetLoadedAgentId] = useState<string | null>(null);
  const [assetSaving, setAssetSaving] = useState<'soul' | 'user' | null>(null);
  const [assetError, setAssetError] = useState('');
  const [assetSuccess, setAssetSuccess] = useState('');
  const [summaryDrafts, setSummaryDrafts] = useState<SummaryDrafts>(emptySummaryDrafts);
  const [summarySaving, setSummarySaving] = useState(false);
  const assetDraftsRef = useRef(emptyAssetDrafts());
  const summaryDraftsRef = useRef<SummaryDrafts>(emptySummaryDrafts());

  const replaceAssetDrafts = (nextDrafts: { soul: string; user: string }) => {
    assetDraftsRef.current = nextDrafts;
    setAssetDrafts(nextDrafts);
  };

  const replaceSummaryDrafts = (nextDrafts: SummaryDrafts) => {
    summaryDraftsRef.current = nextDrafts;
    setSummaryDrafts(nextDrafts);
  };

  const resetAssetState = () => {
    setAgentAssets(null);
    setAgentMemoryStats(null);
    setAgentSkills([]);
    replaceAssetDrafts(emptyAssetDrafts());
    replaceSummaryDrafts(emptySummaryDrafts());
    setAssetLoadedAgentId(null);
    setAssetLoading(false);
  };

  const applyBootstrapBundle = (bootstrapData: AgentAssetBundle, agentId: string) => {
    setAgentAssets(bootstrapData);
    replaceAssetDrafts({
      soul: bootstrapData.files?.soul?.content || '',
      user: bootstrapData.files?.user?.content || '',
    });
    replaceSummaryDrafts(summaryToDrafts(bootstrapData.summary));
    setAssetLoadedAgentId(agentId);
  };

  const handleAssetDraftChange = (fileKind: 'soul' | 'user', value: string) => {
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

  useEffect(() => {
    let disposed = false;

    const loadAgentAssets = async () => {
      if (!selectedAgentId) {
        resetAssetState();
        return;
      }

      const currentAgentId = selectedAgentId;
      setAssetLoading(true);
      setAssetError('');
      setAssetLoadedAgentId(null);
      setAgentAssets(null);
      setAgentMemoryStats(null);
      setAgentSkills([]);
      replaceAssetDrafts(emptyAssetDrafts());
      replaceSummaryDrafts(emptySummaryDrafts());

      try {
        const [bootstrapRes, memoryRes, skillsRes] = await Promise.all([
          fetch(`/api/agents/${currentAgentId}/bootstrap-files`),
          fetch(`/api/memory?agent_id=${encodeURIComponent(currentAgentId)}`),
          fetch(`/api/skills?agent_id=${encodeURIComponent(currentAgentId)}`),
        ]);

        if (!bootstrapRes.ok) {
          const error = await bootstrapRes.json();
          throw new Error(error.detail || 'Failed to load agent bootstrap files');
        }

        const bootstrapData = await bootstrapRes.json();
        const memoryData = memoryRes.ok ? await memoryRes.json() : null;
        const skillsData = skillsRes.ok ? await skillsRes.json() : { skills: [] };

        if (disposed) {
          return;
        }

        applyBootstrapBundle(bootstrapData, currentAgentId);
        setAgentMemoryStats(memoryData ? {
          total_entries: memoryData.total_entries || 0,
          total_size_kb: memoryData.total_size_kb || 0,
        } : null);
        setAgentSkills(skillsData.skills || []);
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
    };
  }, [selectedAgentId]);

  const handleSaveAssetFile = async (fileKind: 'soul' | 'user') => {
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
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save bootstrap file');
      }

      const updated = await fetch(`/api/agents/${selectedAgentId}/bootstrap-files`);
      if (updated.ok) {
        const updatedData = await updated.json();
        applyBootstrapBundle(updatedData, selectedAgentId);
      }

      await onSaved?.();
      setAssetSuccess(fileKind === 'soul' ? 'SOUL.md 已保存' : 'USER.md 已保存');
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
        const error = await response.json();
        throw new Error(error.detail || 'Failed to save summary');
      }

      const updatedData = await response.json();
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
    setAssetError,
    setAssetSuccess,
  };
};
