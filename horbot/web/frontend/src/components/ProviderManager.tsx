import React, { useState, memo } from 'react';
import { configService } from '../services';
import type { AddProviderData } from '../services/config';
import type { ProvidersConfig } from '../types';
import { Modal, Button, Input } from './ui';

interface ProviderManagerProps {
  providers?: ProvidersConfig;
  onProviderAdded: () => void;
}

const ProviderManager: React.FC<ProviderManagerProps> = ({
  providers,
  onProviderAdded,
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [newProvider, setNewProvider] = useState({ name: '', apiKey: '', apiBase: '' });
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const errors: Record<string, string> = {};
    const trimmedName = newProvider.name.trim();
    if (!trimmedName) {
      errors.name = 'Provider name is required';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(trimmedName)) {
      errors.name = 'Provider name can only contain letters, numbers, hyphens, and underscores';
    } else if (providers && trimmedName in providers) {
      errors.name = `Provider "${trimmedName}" already exists`;
    }
    if (newProvider.apiBase && !/^https?:\/\/.+/.test(newProvider.apiBase)) {
      errors.apiBase = 'API Base URL must start with http:// or https://';
    }
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleAddProvider = async () => {
    if (!validate()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const providerData: AddProviderData = {
        apiKey: newProvider.apiKey || undefined,
        apiBase: newProvider.apiBase || undefined,
      };
      await configService.addProvider(newProvider.name.trim(), providerData);

      onProviderAdded();
      setNewProvider({ name: '', apiKey: '', apiBase: '' });
      setValidationErrors({});
      setIsDialogOpen(false);
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail || 
                       (err as Error).message || 'Failed to add provider';
      setError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setIsDialogOpen(false);
    setNewProvider({ name: '', apiKey: '', apiBase: '' });
    setError(null);
    setValidationErrors({});
  };

  return (
    <>
      <button
        onClick={() => setIsDialogOpen(true)}
        data-testid="provider-add-button"
        className="w-full flex items-center justify-center space-x-2 px-4 py-3 border-2 border-dashed border-surface-600 rounded-lg text-surface-400 hover:border-brand-500 hover:text-brand-400 transition-all duration-200"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        <span>添加自定义 Provider</span>
      </button>

      <Modal
        isOpen={isDialogOpen}
        onClose={handleClose}
        title="添加自定义 Provider"
      >
        <div className="space-y-4">
          {error && (
            <div className="bg-semantic-error/20 border border-semantic-error/50 text-semantic-error p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <Input
            label="Provider Name"
            required
            value={newProvider.name}
            onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
            error={validationErrors.name}
            placeholder="例如：my-custom-llm"
            data-testid="provider-name-input"
          />

          <Input
            type="password"
            label="API Key"
            value={newProvider.apiKey}
            onChange={(e) => setNewProvider({ ...newProvider, apiKey: e.target.value })}
            placeholder="输入 API Key（可选）"
            data-testid="provider-api-key-input"
          />

          <Input
            label="API Base URL"
            value={newProvider.apiBase}
            onChange={(e) => setNewProvider({ ...newProvider, apiBase: e.target.value })}
            error={validationErrors.apiBase}
            placeholder="https://api.example.com/v1"
            data-testid="provider-api-base-input"
          />
          <p className="text-sm text-surface-500">
            适合接入 OpenAI 兼容网关、公司内部代理，或暂未内置的第三方模型服务。
          </p>
        </div>

        <div className="flex justify-end space-x-3 mt-6">
          <Button variant="secondary" onClick={handleClose} disabled={isSubmitting}>
            取消
          </Button>
          <Button
            onClick={handleAddProvider}
            disabled={isSubmitting || !newProvider.name.trim()}
            isLoading={isSubmitting}
            data-testid="provider-add-confirm"
          >
            添加 Provider
          </Button>
        </div>
      </Modal>
    </>
  );
};

export default memo(ProviderManager);
