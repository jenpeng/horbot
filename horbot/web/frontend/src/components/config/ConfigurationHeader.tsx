import React from 'react';
import { Button } from '../ui/Button';

interface ConfigurationHeaderProps {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  isValidating: boolean;
  isRefreshing: boolean;
  onValidate: () => void | Promise<void>;
  onReload: () => void;
  onExport: () => void;
  onImport: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const ConfigurationHeader: React.FC<ConfigurationHeaderProps> = ({
  fileInputRef,
  isValidating,
  isRefreshing,
  onValidate,
  onReload,
  onExport,
  onImport,
}) => {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 className="text-3xl font-bold text-surface-900">Configuration</h1>
        <p className="text-base text-surface-600 mt-2">管理 horbot 的全局默认值。主 agent 或其他 agent 的实例覆盖项请到多 Agent 管理页维护。</p>
      </div>
      <div className="flex items-center gap-2 flex-wrap justify-end">
        <Button
          variant="secondary"
          size="md"
          onClick={() => void onValidate()}
          isLoading={isValidating}
          leftIcon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        >
          检查配置
        </Button>
        <Button
          variant="secondary"
          size="md"
          onClick={onReload}
          isLoading={isRefreshing}
          leftIcon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          }
        >
          重新加载
        </Button>
        <Button
          variant="secondary"
          size="md"
          onClick={() => fileInputRef.current?.click()}
          leftIcon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          }
        >
          导入配置
        </Button>
        <Button
          variant="secondary"
          size="md"
          onClick={onExport}
          leftIcon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          }
        >
          导出配置
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={onImport}
          className="hidden"
        />
      </div>
    </div>
  );
};

export default ConfigurationHeader;
