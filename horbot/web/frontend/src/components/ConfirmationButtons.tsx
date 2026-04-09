import React from 'react';

interface ConfirmationButtonsProps {
  confirmationId: string;
  toolName: string;
  toolArguments: Record<string, any>;
  onConfirm: (confirmationId: string) => void;
  onCancel: (confirmationId: string) => void;
  disabled?: boolean;
}

const ConfirmationButtons: React.FC<ConfirmationButtonsProps> = ({
  confirmationId,
  toolName,
  toolArguments,
  onConfirm,
  onCancel,
  disabled = false,
}) => {
  // Format tool arguments for display
  const formatArguments = (args: Record<string, any>): string => {
    try {
      return JSON.stringify(args, null, 2);
    } catch {
      return String(args);
    }
  };

  return (
    <div className="mt-4 p-4 bg-amber-900/30 border border-amber-700/50 rounded-xl">
      <div className="flex items-start gap-3 mb-3">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-amber-600/20 flex items-center justify-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 text-amber-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-amber-200 font-medium mb-1">需要确认</p>
          <p className="text-gray-300 text-sm">
            AI 想要执行工具 <code className="bg-secondary-700 px-1.5 py-0.5 rounded text-amber-300">{toolName}</code>
          </p>
          {toolArguments && Object.keys(toolArguments).length > 0 && (
            <div className="mt-2">
              <p className="text-gray-400 text-xs mb-1">参数:</p>
              <pre className="bg-secondary-800/50 rounded-lg p-2 text-xs text-gray-300 overflow-x-auto">
                {formatArguments(toolArguments)}
              </pre>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-3 justify-end">
        <button
          onClick={() => onCancel(confirmationId)}
          disabled={disabled}
          className="px-4 py-2 text-sm text-gray-300 hover:text-white bg-secondary-700 hover:bg-secondary-600 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          取消
        </button>
        <button
          onClick={() => onConfirm(confirmationId)}
          disabled={disabled}
          className="px-4 py-2 text-sm text-white bg-amber-600 hover:bg-amber-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          确认执行
        </button>
      </div>
    </div>
  );
};

export default ConfirmationButtons;
