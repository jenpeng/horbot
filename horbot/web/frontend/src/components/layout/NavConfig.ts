import { LayoutDashboard, MessageSquare, Sparkles, ListTodo, Users, Radio, Activity, Coins, Settings } from 'lucide-react';

export interface NavItem {
  path: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string | number;
  badgeVariant?: 'default' | 'success' | 'warning' | 'error' | 'info';
}

export const navItems: NavItem[] = [
  { path: '/', label: '控制台', icon: LayoutDashboard },
  { path: '/chat', label: '对话', icon: MessageSquare, badge: '3', badgeVariant: 'info' },
  { path: '/skills', label: '技能', icon: Sparkles, badge: 'New', badgeVariant: 'success' },
  { path: '/tasks', label: '任务', icon: ListTodo },
  { path: '/teams', label: '团队', icon: Users },
  { path: '/channels', label: '通道', icon: Radio },
  { path: '/status', label: '状态', icon: Activity },
  { path: '/tokens', label: 'Token统计', icon: Coins },
  { path: '/config', label: '设置', icon: Settings },
];
