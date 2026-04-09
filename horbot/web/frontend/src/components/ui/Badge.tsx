import React from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'primary' | 'accent';
type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  pulse?: boolean;
  gradient?: boolean;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-surface-100 text-surface-700',
  success: 'bg-accent-emerald/10 text-accent-emerald',
  warning: 'bg-accent-orange/10 text-accent-orange',
  error: 'bg-accent-red/10 text-accent-red',
  info: 'bg-primary-100 text-primary-700',
  primary: 'bg-primary-100 text-primary-700',
  accent: 'bg-accent-purple/10 text-accent-purple',
};

const gradientClasses: Record<BadgeVariant, string> = {
  default: 'bg-gradient-to-r from-surface-200 to-surface-300 text-surface-900',
  success: 'bg-gradient-to-r from-accent-emerald to-accent-teal text-white',
  warning: 'bg-gradient-to-r from-accent-orange to-accent-yellow text-white',
  error: 'bg-gradient-to-r from-accent-red to-accent-orange text-white',
  info: 'bg-gradient-to-r from-primary-500 to-primary-600 text-white',
  primary: 'bg-gradient-to-r from-primary-500 to-accent-indigo text-white',
  accent: 'bg-gradient-to-r from-accent-purple to-accent-pink text-white',
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: 'px-3 py-1.5 text-xs rounded-md',
  md: 'px-4 py-2 text-sm rounded-lg',
  lg: 'px-5 py-2.5 text-base rounded-xl',
};

const dotColors: Record<BadgeVariant, string> = {
  default: 'bg-surface-600',
  success: 'bg-accent-emerald',
  warning: 'bg-accent-orange',
  error: 'bg-accent-red',
  info: 'bg-primary-500',
  primary: 'bg-primary-500',
  accent: 'bg-accent-purple',
};

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  pulse = false,
  gradient = false,
  className = '',
}) => {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 font-semibold leading-tight
        ${gradient ? gradientClasses[variant] : variantClasses[variant]}
        ${sizeClasses[size]}
        ${className}
      `}
    >
      {dot && <span className={`w-2 h-2 rounded-full ${dotColors[variant]} ${pulse ? 'animate-pulse' : ''}`} />}
      {children}
    </span>
  );
};

interface TagProps {
  children: React.ReactNode;
  color?: 'blue' | 'purple' | 'pink' | 'cyan' | 'green' | 'orange' | 'red' | 'yellow' | 'indigo';
  size?: 'sm' | 'md' | 'lg';
  gradient?: boolean;
  className?: string;
  onClick?: () => void;
}

const tagColors: Record<string, string> = {
  blue: 'bg-primary-100 text-primary-700',
  purple: 'bg-accent-purple/10 text-accent-purple',
  pink: 'bg-accent-pink/10 text-accent-pink',
  cyan: 'bg-accent-cyan/10 text-accent-cyan',
  green: 'bg-accent-emerald/10 text-accent-emerald',
  orange: 'bg-accent-orange/10 text-accent-orange',
  red: 'bg-accent-red/10 text-accent-red',
  yellow: 'bg-accent-yellow/10 text-accent-yellow',
  indigo: 'bg-accent-indigo/10 text-accent-indigo',
};

const tagGradientColors: Record<string, string> = {
  blue: 'bg-gradient-to-r from-primary-500 to-primary-600 text-white',
  purple: 'bg-gradient-to-r from-accent-purple to-accent-violet text-white',
  pink: 'bg-gradient-to-r from-accent-pink to-accent-fuchsia text-white',
  cyan: 'bg-gradient-to-r from-accent-cyan to-accent-teal text-white',
  green: 'bg-gradient-to-r from-accent-emerald to-accent-teal text-white',
  orange: 'bg-gradient-to-r from-accent-orange to-accent-yellow text-white',
  red: 'bg-gradient-to-r from-accent-red to-accent-orange text-white',
  yellow: 'bg-gradient-to-r from-accent-yellow to-accent-orange text-white',
  indigo: 'bg-gradient-to-r from-accent-indigo to-accent-purple text-white',
};

const tagSizes: Record<string, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
};

export const Tag: React.FC<TagProps> = ({
  children,
  color = 'blue',
  size = 'md',
  gradient = false,
  className = '',
  onClick,
}) => {
  return (
    <span
      className={`
        inline-flex items-center font-semibold rounded-lg
        ${tagSizes[size]}
        ${onClick ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}
        ${gradient ? tagGradientColors[color] : tagColors[color]}
        ${className}
      `}
      onClick={onClick}
    >
      {children}
    </span>
  );
};

export default Badge;
