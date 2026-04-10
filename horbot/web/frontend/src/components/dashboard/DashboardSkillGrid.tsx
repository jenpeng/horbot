import { AI_SKILLS } from './constants';

interface DashboardSkillGridProps {
  onSkillClick: (skillId: string) => void;
}

const DashboardSkillGrid = ({ onSkillClick }: DashboardSkillGridProps) => (
  <div>
    <div className="mb-5 flex items-center justify-between">
      <div>
        <h2 className="text-xl font-semibold text-surface-900 tracking-tight">AI Assistant Skills</h2>
        <p className="text-sm text-surface-500 mt-1.5 font-light">Quick access to common features</p>
      </div>
      <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-surface-100 rounded-full">
        <span className="w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
        <span className="text-xs font-medium text-surface-600">{AI_SKILLS.length} 项可用</span>
      </div>
    </div>
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {AI_SKILLS.map((skill, index) => (
        <div
          key={skill.id}
          onClick={() => onSkillClick(skill.id)}
          className="
            relative overflow-hidden
            bg-white border border-surface-200/80 rounded-2xl p-5
            cursor-pointer transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]
            hover:shadow-xl hover:-translate-y-2 hover:border-transparent
            group
            active:scale-[0.98] active:transition-all active:duration-150
          "
          style={{
            animationDelay: `${index * 60}ms`,
            boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)',
          }}
        >
          <div className={`absolute inset-0 bg-gradient-to-br ${skill.gradient} opacity-0 group-hover:opacity-100 transition-all duration-500 ease-out`} style={{ mixBlendMode: 'overlay' }} />
          <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${skill.gradient} opacity-0 group-hover:opacity-15 transition-opacity duration-500 -z-10`} style={{ margin: '-1px' }} />
          <div className={`absolute -top-8 -right-8 w-24 h-24 bg-gradient-to-br ${skill.gradient} opacity-0 group-hover:opacity-10 transition-all duration-700 ease-out rounded-full blur-2xl transform group-hover:scale-150`} />

          <div className={`relative w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-all duration-500 ease-out group-hover:scale-110 group-hover:shadow-lg ${skill.shadowColor} bg-gradient-to-br ${skill.gradient}`}>
            <div className="text-white drop-shadow-sm">{skill.icon}</div>
            <div className="absolute inset-0 rounded-xl bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-md" />
          </div>

          <div className="relative">
            <h3 className="text-[15px] font-semibold text-surface-900 mb-1.5 tracking-tight group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-surface-900 group-hover:to-surface-700 transition-all duration-300">
              {skill.title}
            </h3>
            <p className="text-[13px] text-surface-500 leading-relaxed group-hover:text-surface-600 transition-colors duration-300">
              {skill.description}
            </p>
          </div>

          <div className="absolute top-5 right-5 opacity-0 group-hover:opacity-100 transform translate-x-3 group-hover:translate-x-0 transition-all duration-400 ease-out">
            <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${skill.gradient} flex items-center justify-center shadow-lg group-hover:shadow-xl transition-shadow duration-300`}>
              <svg className="w-4 h-4 text-white transform group-hover:translate-x-0.5 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </div>
          </div>

          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
            <div className="absolute inset-0 bg-gradient-to-br from-white/30 to-transparent opacity-0 group-active:opacity-100 transition-opacity duration-150" />
          </div>
        </div>
      ))}
    </div>
  </div>
);

export default DashboardSkillGrid;
