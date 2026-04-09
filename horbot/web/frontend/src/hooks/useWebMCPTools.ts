import { useEffect, useCallback, useState } from 'react';
import { getAllTools } from '../services/webmcp';

interface UseWebMCPToolsResult {
  isSupported: boolean;
  isRegistered: boolean;
  error: string | null;
  toolCount: number;
}

export const useWebMCPTools = (): UseWebMCPToolsResult => {
  const [isSupported, setIsSupported] = useState(false);
  const [isRegistered, setIsRegistered] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toolCount, setToolCount] = useState(0);

  const registerTools = useCallback(async () => {
    if (!navigator.mcp) {
      console.log('[WebMCP] navigator.mcp 不可用');
      return;
    }

    const tools = getAllTools();
    setToolCount(tools.length);
    console.log(`[WebMCP] 准备注册 ${tools.length} 个工具`);
    console.log('[WebMCP] navigator.mcp 对象:', navigator.mcp);
    console.log('[WebMCP] 可用方法:', Object.keys(navigator.mcp));

    let successCount = 0;
    let failCount = 0;

    for (const tool of tools) {
      try {
        console.log(`[WebMCP] 正在注册工具: ${tool.name}`);
        await navigator.mcp.registerTool({
          name: tool.name,
          description: tool.description,
          inputSchema: tool.inputSchema,
          outputSchema: tool.outputSchema,
          execute: tool.execute,
        });
        console.log(`[WebMCP] ✓ 工具注册成功: ${tool.name}`);
        successCount++;
      } catch (err) {
        console.error(`[WebMCP] ✗ 工具注册失败: ${tool.name}`, err);
        failCount++;
      }
    }

    console.log(`[WebMCP] 注册完成: 成功 ${successCount}, 失败 ${failCount}`);

    if (navigator.mcp.getTools) {
      try {
        const registeredTools = await navigator.mcp.getTools();
        console.log(`[WebMCP] 已注册的工具列表 (${registeredTools?.length || 0} 个):`, registeredTools);
      } catch (err) {
        console.error('[WebMCP] 获取工具列表失败:', err);
      }
    }

    if (failCount === 0) {
      setIsRegistered(true);
      setError(null);
    } else {
      setError(`${failCount} 个工具注册失败`);
      setIsRegistered(successCount > 0);
    }
  }, []);

  const unregisterTools = useCallback(async () => {
    if (!navigator.mcp || !isRegistered) {
      return;
    }

    const tools = getAllTools();
    try {
      for (const tool of tools) {
        await navigator.mcp.unregisterTool(tool.name);
      }
      setIsRegistered(false);
      console.log('[WebMCP] 所有工具已注销');
    } catch (err) {
      console.error('[WebMCP] 注销工具失败:', err);
    }
  }, [isRegistered]);

  useEffect(() => {
    const supported = typeof navigator !== 'undefined' && 'mcp' in navigator;
    console.log(`[WebMCP] 浏览器支持检测: ${supported}`);
    console.log(`[WebMCP] navigator 对象:`, navigator);
    console.log(`[WebMCP] navigator.mcp:`, (navigator as Navigator & { mcp?: unknown }).mcp);
    
    setIsSupported(supported);

    if (supported) {
      registerTools();
    }

    return () => {
      if (supported) {
        unregisterTools();
      }
    };
  }, [registerTools, unregisterTools]);

  return {
    isSupported,
    isRegistered,
    error,
    toolCount,
  };
};

export default useWebMCPTools;
