import { useEffect } from 'react';
import { useWebMCPTools } from '../hooks';

const WebMCPBootstrap: React.FC = () => {
  const { isSupported, isRegistered, error, toolCount } = useWebMCPTools();

  useEffect(() => {
    if (!isSupported) {
      return;
    }

    console.log('[WebMCP] 浏览器支持 WebMCP');
    if (isRegistered) {
      console.log(`[WebMCP] 已注册 ${toolCount} 个工具`);
    }
    if (error) {
      console.error('[WebMCP] 注册失败:', error);
    }
  }, [isSupported, isRegistered, error, toolCount]);

  return null;
};

export default WebMCPBootstrap;
