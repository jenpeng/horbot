interface DashboardFixResultProps {
  fixResult: {
    fixed: Array<{ issue: string; message: string }>;
    failed: Array<{ issue: string; error: string }>;
    suggestions: Array<{ issue: string; message: string; action: string }>;
  };
}

const DashboardFixResult = ({ fixResult }: DashboardFixResultProps) => (
  <div className="space-y-4">
    {fixResult.fixed.length > 0 && (
      <div className="bg-green-50 rounded-xl p-4 border border-green-200">
        <h4 className="text-sm font-semibold text-green-700 mb-3 flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          已修复 ({fixResult.fixed.length} 项)
        </h4>
        <ul className="space-y-2">
          {fixResult.fixed.map((item, index) => (
            <li key={index} className="text-sm text-green-700 flex items-start gap-2">
              <span className="text-green-500 mt-0.5">•</span>
              <span>{item.message}</span>
            </li>
          ))}
        </ul>
      </div>
    )}

    {fixResult.failed.length > 0 && (
      <div className="bg-red-50 rounded-xl p-4 border border-red-200">
        <h4 className="text-sm font-semibold text-red-700 mb-3 flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          修复失败 ({fixResult.failed.length} 项)
        </h4>
        <ul className="space-y-2">
          {fixResult.failed.map((item, index) => (
            <li key={index} className="text-sm text-red-700">
              <span className="font-medium">{item.issue}:</span> {item.error}
            </li>
          ))}
        </ul>
      </div>
    )}

    {fixResult.suggestions.length > 0 && (
      <div className="bg-amber-50 rounded-xl p-4 border border-amber-200">
        <h4 className="text-sm font-semibold text-amber-700 mb-3 flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          建议手动处理 ({fixResult.suggestions.length} 项)
        </h4>
        <ul className="space-y-2">
          {fixResult.suggestions.map((item, index) => (
            <li key={index} className="text-sm text-amber-700 flex items-start gap-2">
              <span className="text-amber-500 mt-0.5">•</span>
              <span>{item.message}</span>
            </li>
          ))}
        </ul>
      </div>
    )}

    {fixResult.fixed.length === 0 && fixResult.failed.length === 0 && fixResult.suggestions.length === 0 && (
      <div className="bg-surface-50 rounded-xl p-6 border border-surface-200 text-center">
        <svg className="w-12 h-12 mx-auto text-surface-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-surface-600">系统状态良好，无需修复</p>
      </div>
    )}
  </div>
);

export default DashboardFixResult;
