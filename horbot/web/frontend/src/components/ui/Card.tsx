import React from 'react';

type CardVariant = 'default' | 'gradient' | 'elevated' | 'outlined';
type CardPadding = 'none' | 'sm' | 'md' | 'lg';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  variant?: CardVariant;
  padding?: CardPadding;
  hover?: boolean;
  gradient?: 'primary' | 'secondary' | 'accent' | 'success' | 'vibrant' | 'custom';
  onClick?: () => void;
}

const paddingClasses: Record<CardPadding, string> = {
  none: '',
  sm: 'p-5',
  md: 'p-6',
  lg: 'p-8',
};

const variantClasses: Record<CardVariant, string> = {
  default: 'bg-white border border-surface-200 shadow-sm',
  gradient: 'bg-gradient-to-br border-none',
  elevated: 'bg-white border border-surface-200 shadow-lg',
  outlined: 'bg-white border-2 border-surface-300 shadow-none',
};

const gradientClasses: Record<string, string> = {
  primary: 'from-primary-50 to-primary-100/50',
  secondary: 'from-surface-50 to-surface-100',
  accent: 'from-accent-purple/10 to-accent-pink/10',
  success: 'from-accent-emerald/10 to-accent-teal/10',
  vibrant: 'from-primary-500 to-accent-indigo',
  custom: '',
};

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  variant = 'default',
  padding = 'md',
  hover = false,
  gradient = 'primary',
  onClick,
  ...rest
}) => {
  return (
    <div
      className={`
        relative rounded-2xl
        ${variantClasses[variant]}
        ${variant === 'gradient' ? gradientClasses[gradient] : ''}
        ${paddingClasses[padding]}
        ${hover || onClick ? 'cursor-pointer' : ''}
        transition-all duration-300
        ${hover ? 'hover:border-primary-300 hover:shadow-card-hover hover:-translate-y-0.5' : ''}
        ${className}
      `}
      onClick={onClick}
      {...rest}
    >
      {children}
    </div>
  );
};

interface CardHeaderProps {
  title: React.ReactNode;
  subtitle?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  iconVariant?: 'default' | 'gradient' | 'primary' | 'success' | 'warning' | 'error';
  className?: string;
}

const iconVariantClasses: Record<string, string> = {
  default: 'bg-surface-100 text-surface-600',
  gradient: 'bg-gradient-to-br from-primary-500 to-accent-violet text-white shadow-md',
  primary: 'bg-primary-100 text-primary-600',
  success: 'bg-accent-emerald/10 text-accent-emerald',
  warning: 'bg-accent-orange/10 text-accent-orange',
  error: 'bg-accent-red/10 text-accent-red',
};

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  subtitle,
  action,
  icon,
  iconVariant = 'default',
  className = '',
}) => {
  return (
    <div className={`flex items-start justify-between mb-6 ${className}`}>
      <div className="flex items-center gap-4">
        {icon && (
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-sm ${iconVariantClasses[iconVariant]}`}>
            {icon}
          </div>
        )}
        <div>
          <h3 className="text-xl font-semibold text-surface-900">{title}</h3>
          {subtitle && <p className="text-sm text-surface-600 mt-1">{subtitle}</p>}
        </div>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
};

interface CardContentProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

const contentPaddingClasses = {
  none: '',
  sm: 'p-5',
  md: 'p-6',
  lg: 'p-8',
};

export const CardContent: React.FC<CardContentProps> = ({ children, className = '', padding = 'none' }) => {
  return <div className={`${contentPaddingClasses[padding]} ${className}`}>{children}</div>;
};

interface CardFooterProps {
  children: React.ReactNode;
  className?: string;
  bordered?: boolean;
}

export const CardFooter: React.FC<CardFooterProps> = ({ children, className = '', bordered = true }) => {
  return (
    <div className={`mt-6 pt-6 ${bordered ? 'border-t border-surface-200' : ''} ${className}`}>
      {children}
    </div>
  );
};

export default Card;
