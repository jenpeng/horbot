import { useEffect, useState } from 'react';
import { useToast, type ToastType } from '../contexts/ToastContext';

interface SingleToastProps {
  message: string;
  type: ToastType;
  onClose: () => void;
  duration?: number;
}

const SingleToast: React.FC<SingleToastProps> = ({ message, type, onClose, duration = 3000 }) => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => {
      setIsVisible(true);
    });

    if (duration > 0) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(onClose, 300);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 300);
  };

  const baseClasses = 'fixed top-4 right-4 z-50 max-w-md p-4 rounded-xl shadow-lg transition-all duration-300 flex items-center justify-between border';
  const visibilityClasses = isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-full';
  
  const typeClasses = {
    success: 'bg-accent-emerald/95 border-accent-emerald text-white',
    error: 'bg-accent-red/95 border-accent-red text-white',
    info: 'bg-primary-500/95 border-primary-500 text-white',
    warning: 'bg-accent-orange/95 border-accent-orange text-white',
  };

  const icons = {
    success: (
      <svg className="h-5 w-5 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    error: (
      <svg className="h-5 w-5 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    info: (
      <svg className="h-5 w-5 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    warning: (
      <svg className="h-5 w-5 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  };

  return (
    <div className={`${baseClasses} ${visibilityClasses} ${typeClasses[type]}`}>
      <div className="flex items-center">
        {icons[type]}
        <span className="text-sm font-medium">{message}</span>
      </div>
      <button
        onClick={handleClose}
        className="ml-4 p-1 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};

const Toast: React.FC = () => {
  const { toasts, remove } = useToast();

  return (
    <>
      {toasts.map((toast, index) => (
        <div key={toast.id} style={{ top: `${(index * 80) + 16}px` }} className="fixed right-4 z-50">
          <SingleToast
            message={toast.message}
            type={toast.type}
            duration={toast.duration}
            onClose={() => remove(toast.id)}
          />
        </div>
      ))}
    </>
  );
};

export default Toast;
