import type { ComponentType } from 'react';
import { LayoutDashboard, MessageSquare, Sparkles, ListTodo, Users, Radio, Activity, Coins, Settings } from 'lucide-react';

export interface NavItem {
  path: string;
  labelKey: string;
  icon: ComponentType<{ className?: string }>;
  badgeKey?: string;
  badge?: string | number;
  badgeVariant?: 'default' | 'success' | 'warning' | 'error' | 'info';
}

export const navItems: NavItem[] = [
  { path: '/', labelKey: 'nav.dashboard', icon: LayoutDashboard },
  { path: '/chat', labelKey: 'nav.chat', icon: MessageSquare, badge: '3', badgeVariant: 'info' },
  { path: '/skills', labelKey: 'nav.skills', icon: Sparkles, badgeKey: 'navBadge.new', badgeVariant: 'success' },
  { path: '/tasks', labelKey: 'nav.tasks', icon: ListTodo },
  { path: '/teams', labelKey: 'nav.teams', icon: Users },
  { path: '/channels', labelKey: 'nav.channels', icon: Radio },
  { path: '/status', labelKey: 'nav.status', icon: Activity },
  { path: '/tokens', labelKey: 'nav.tokens', icon: Coins },
  { path: '/config', labelKey: 'nav.config', icon: Settings },
];
