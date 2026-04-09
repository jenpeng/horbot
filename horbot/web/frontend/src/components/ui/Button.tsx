import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'accent' | 'ghost' | 'danger' | 'success' | 'outline';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: `
    bg-gradient-to-r from-primary-500 to-primary-600 text-white
    hover:from-primary-600 hover:to-primary-700
    active:from-primary-700 active:to-primary-800
    shadow-md shadow-primary-500/25 hover:shadow-lg hover:shadow-primary-500/30
    hover:-translate-y-0.5
  `,
  secondary: `
    bg-white text-surface-700
    border border-surface-300
    hover:bg-surface-50 hover:border-surface-400
    shadow-sm hover:shadow-md
    hover:-translate-y-0.5
  `,
  accent: `
    bg-gradient-to-r from-accent-purple to-accent-pink text-white
    hover:from-accent-violet hover:to-accent-fuchsia
    active:from-purple-700 active:to-pink-700
    shadow-md shadow-accent-purple/25 hover:shadow-lg hover:shadow-accent-purple/30
    hover:-translate-y-0.5
  `,
  ghost: `
    bg-transparent text-surface-600
    hover:bg-surface-100 hover:text-surface-900
  `,
  danger: `
    bg-gradient-to-r from-accent-red to-accent-orange text-white
    hover:from-red-600 hover:to-orange-600
    active:from-red-700 active:to-orange-700
    shadow-md shadow-accent-red/25 hover:shadow-lg hover:shadow-accent-red/30
    hover:-translate-y-0.5
  `,
  success: `
    bg-gradient-to-r from-accent-emerald to-accent-teal text-white
    hover:from-emerald-600 hover:to-teal-600
    active:from-emerald-700 active:to-teal-700
    shadow-md shadow-accent-emerald/25 hover:shadow-lg hover:shadow-accent-emerald/30
    hover:-translate-y-0.5
  `,
  outline: `
    bg-transparent text-primary-600
    border-2 border-primary-500
    hover:bg-primary-50 hover:border-primary-600
    hover:-translate-y-0.5
  `,
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-4 py-2 text-sm rounded-lg gap-1.5',
  md: 'px-5 py-2.5 text-base rounded-xl gap-2',
  lg: 'px-6 py-3 text-lg rounded-xl gap-2.5',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'secondary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  children,
  className = '',
  disabled,
  ...props
}) => {
  return (
    <button
      className={`
        relative inline-flex items-center justify-center
        font-semibold
        transition-all duration-200
        disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0
        disabled:saturate-0 disabled:bg-surface-300
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${className}
      `}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && (
        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {!isLoading && leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
      {children}
      {!isLoading && rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </button>
  );
};

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'ghost' | 'primary' | 'accent';
  size?: 'sm' | 'md' | 'lg';
}

const iconButtonVariants = {
  default: 'bg-white text-surface-600 border border-surface-300 hover:bg-surface-50 hover:text-surface-900 hover:border-surface-400 shadow-sm',
  ghost: 'bg-transparent text-surface-600 hover:bg-surface-100 hover:text-surface-900',
  primary: 'bg-primary-500 text-white hover:bg-primary-600 shadow-sm',
  accent: 'bg-gradient-to-r from-accent-purple to-accent-pink text-white hover:from-accent-violet hover:to-accent-fuchsia shadow-sm',
};

const iconButtonSizes = {
  sm: 'w-8 h-8',
  md: 'w-10 h-10',
  lg: 'w-12 h-12',
};

export const IconButton: React.FC<IconButtonProps> = ({
  children,
  className = '',
  variant = 'default',
  size = 'md',
  ...props
}) => {
  return (
    <button
      className={`
        inline-flex items-center justify-center
        rounded-lg
        transition-all duration-200
        disabled:opacity-40 disabled:cursor-not-allowed
        disabled:saturate-0 disabled:bg-surface-300
        ${iconButtonVariants[variant]}
        ${iconButtonSizes[size]}
        ${className}
      `}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;
