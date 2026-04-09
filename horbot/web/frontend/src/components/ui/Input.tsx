import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  success?: boolean;
  hint?: string;
  icon?: React.ReactNode;
  className?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  success,
  hint,
  icon,
  className = '',
  ...props
}) => {
  const baseClasses = `
    w-full px-4 py-2.5
    bg-white
    border-2 rounded-lg
    text-base text-surface-900
    placeholder:text-surface-400
    transition-all duration-200
    focus:outline-none
    disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-surface-50
  `;

  const stateClasses = error
    ? 'border-accent-red focus:border-accent-red focus:ring-4 focus:ring-accent-red/10'
    : success
    ? 'border-accent-emerald focus:border-accent-emerald focus:ring-4 focus:ring-accent-emerald/10'
    : 'border-surface-300 focus:border-primary-500 focus:ring-4 focus:ring-primary-500/10';

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-surface-700 mb-2">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-surface-400">
            {icon}
          </div>
        )}
        <input
          className={`
            ${baseClasses}
            ${stateClasses}
            ${icon ? 'pl-11' : ''}
          `}
          {...props}
        />
      </div>
      {error && (
        <p className="mt-2 text-sm text-accent-red flex items-center gap-1.5">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </p>
      )}
      {hint && !error && (
        <p className="mt-2 text-sm text-surface-500">{hint}</p>
      )}
    </div>
  );
};

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  className?: string;
}

export const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  hint,
  className = '',
  ...props
}) => {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-surface-700 mb-2">
          {label}
        </label>
      )}
      <textarea
        className={`
          w-full px-4 py-3
          bg-white
          border-2 rounded-lg
          text-base text-surface-900
          placeholder:text-surface-400
          transition-all duration-200
          focus:outline-none
          disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-surface-50
          resize-none
          ${error 
            ? 'border-accent-red focus:border-accent-red focus:ring-4 focus:ring-accent-red/10' 
            : 'border-surface-300 focus:border-primary-500 focus:ring-4 focus:ring-primary-500/10'}
        `}
        {...props}
      />
      {error && (
        <p className="mt-2 text-sm text-accent-red flex items-center gap-1.5">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </p>
      )}
      {hint && !error && (
        <p className="mt-2 text-sm text-surface-500">{hint}</p>
      )}
    </div>
  );
};

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: Array<{ value: string; label: string }>;
  className?: string;
}

export const Select: React.FC<SelectProps> = ({
  label,
  error,
  hint,
  options,
  className = '',
  ...props
}) => {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-surface-700 mb-2">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          className={`
            w-full px-4 py-2.5 pr-10
            bg-white
            border-2 rounded-lg
            text-base text-surface-900
            transition-all duration-200
            focus:outline-none
            disabled:opacity-40 disabled:cursor-not-allowed disabled:bg-surface-50
            appearance-none cursor-pointer
            ${error 
              ? 'border-accent-red focus:border-accent-red focus:ring-4 focus:ring-accent-red/10' 
              : 'border-surface-300 focus:border-primary-500 focus:ring-4 focus:ring-primary-500/10'}
          `}
          {...props}
        >
          {options.map(option => (
            <option key={option.value} value={option.value} className="bg-white text-surface-900">
              {option.label}
            </option>
          ))}
        </select>
        <div className="absolute right-3.5 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      {error && (
        <p className="mt-2 text-sm text-accent-red flex items-center gap-1.5">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </p>
      )}
      {hint && !error && (
        <p className="mt-2 text-sm text-surface-500">{hint}</p>
      )}
    </div>
  );
};

export default Input;
