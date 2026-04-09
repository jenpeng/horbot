import React, { useState, useEffect } from 'react';

interface ValidationRule {
  required?: boolean;
  pattern?: RegExp;
  minLength?: number;
  maxLength?: number;
  custom?: (value: string) => string | null;
}

interface ConfigInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'password' | 'number';
  placeholder?: string;
  validation?: ValidationRule;
  disabled?: boolean;
  className?: string;
  min?: number;
  max?: number;
  step?: number | string;
}

const ConfigInput: React.FC<ConfigInputProps> = ({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  validation,
  disabled = false,
  className = '',
  min,
  max,
  step,
}) => {
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (touched && validation) {
      const validationError = validateValue(value);
      setError(validationError);
    }
  }, [value, touched, validation]);

  const validateValue = (val: string): string | null => {
    if (!validation) return null;

    if (validation.required && !val.trim()) {
      return `${label} is required`;
    }

    if (validation.minLength && val.length < validation.minLength) {
      return `${label} must be at least ${validation.minLength} characters`;
    }

    if (validation.maxLength && val.length > validation.maxLength) {
      return `${label} must be at most ${validation.maxLength} characters`;
    }

    if (validation.pattern && val && !validation.pattern.test(val)) {
      return `Invalid ${label.toLowerCase()} format`;
    }

    if (validation.custom && val) {
      return validation.custom(val);
    }

    return null;
  };

  const handleBlur = () => {
    setTouched(true);
    if (validation) {
      const validationError = validateValue(value);
      setError(validationError);
    }
  };

  return (
    <div className={className}>
      <label className="block text-sm font-semibold mb-2 text-surface-700">
        {label}
        {validation?.required && <span className="text-accent-red ml-1">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={handleBlur}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        className={`w-full bg-white border-2 rounded-xl px-4 py-3 text-surface-900 placeholder:text-surface-400 focus:outline-none focus:ring-4 transition-all duration-200 ${
          error
            ? 'border-accent-red focus:ring-accent-red/20'
            : 'border-surface-300 focus:border-primary-500 focus:ring-primary-500/20'
        } ${disabled ? 'opacity-50 cursor-not-allowed bg-surface-50' : ''}`}
        placeholder={placeholder}
      />
      {error && (
        <p className="mt-2 px-3 py-2 bg-accent-red/5 border border-accent-red/20 rounded-lg text-sm text-accent-red flex items-center gap-1.5">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </p>
      )}
    </div>
  );
};

export default ConfigInput;

export const validationRules = {
  apiKey: {
    required: false,
    minLength: 8,
    custom: (value: string) => {
      if (value && value.length < 8) {
        return 'API key seems too short';
      }
      return null;
    },
  },
  url: {
    required: false,
    pattern: /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/,
    custom: (value: string) => {
      if (value && !value.startsWith('http://') && !value.startsWith('https://')) {
        return 'URL should start with http:// or https://';
      }
      return null;
    },
  },
  model: {
    required: true,
    minLength: 1,
  },
};
