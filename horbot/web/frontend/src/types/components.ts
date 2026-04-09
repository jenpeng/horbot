import type { ReactNode, HTMLAttributes, ButtonHTMLAttributes } from 'react';

export interface BaseComponentProps {
  className?: string;
  children?: ReactNode;
}

export interface ModalProps extends BaseComponentProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showClose?: boolean;
}

export interface CardProps extends BaseComponentProps {
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
  onClick?: () => void;
}

export interface CardHeaderProps extends BaseComponentProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export interface CardContentProps extends BaseComponentProps {}

export interface CardFooterProps extends BaseComponentProps {}

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
  iconPosition?: 'left' | 'right';
  children?: ReactNode;
}

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  icon: ReactNode;
  label: string;
}

export interface InputProps extends HTMLAttributes<HTMLInputElement> {
  type?: 'text' | 'password' | 'email' | 'number' | 'search';
  value?: string;
  defaultValue?: string;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
  icon?: ReactNode;
}

export interface BadgeProps extends BaseComponentProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
}

export interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
  onClose: () => void;
}

export interface TabNavProps extends BaseComponentProps {
  tabs: Array<{
    id: string;
    label: string;
    icon?: ReactNode;
    count?: number;
  }>;
  activeTab: string;
  onChange: (tabId: string) => void;
}

export interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'busy' | 'error';
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

export interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'danger';
  onConfirm: () => void;
  onCancel: () => void;
}

export interface SearchInputProps extends BaseComponentProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
}

export interface ExecutionTimelineProps extends BaseComponentProps {
  steps: Array<{
    id: string;
    title: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    timestamp?: string;
    details?: Record<string, unknown>;
  }>;
  activeStepId?: string;
  onStepClick?: (stepId: string) => void;
}

export interface ProviderCardProps extends BaseComponentProps {
  name: string;
  config: {
    apiKey?: string;
    apiBase?: string;
    extraHeaders?: Record<string, string>;
  };
  isDefault?: boolean;
  onEdit: () => void;
  onDelete?: () => void;
}

export interface ConfigSectionProps extends BaseComponentProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  collapsible?: boolean;
  defaultExpanded?: boolean;
}

export interface ConfigInputProps extends BaseComponentProps {
  label: string;
  type?: 'text' | 'password' | 'number' | 'url';
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  helpText?: string;
  error?: string;
  disabled?: boolean;
}
