import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent, Badge, Skeleton } from '../components/ui';
import { statusService, channelsService, diagnosticsService } from '../services';
import type { DashboardChannelSummary, DashboardSummary, SystemStatus } from '../types';
import DiagnosticModal from '../components/DiagnosticModal';
import ConfigCheckResult from '../components/ConfigCheckResult';
import type { ConfigCheckResultData } from '../components/ConfigCheckResult';
import GatewayDiagnosticsResult from '../components/GatewayDiagnosticsResult';
import type { GatewayDiagnosticsData } from '../components/GatewayDiagnosticsResult';
import EnvironmentDetectionResult from '../components/EnvironmentDetectionResult';
import type { EnvironmentDetectionData } from '../components/EnvironmentDetectionResult';
import type { MemoryData } from '../services/diagnostics';
import ConfirmDialog from '../components/ConfirmDialog';

// 技能配置 - 添加渐变背景和动效配置
const AI_SKILLS = [
  {
    id: 'config-check',
    title: 'Config Check',
    description: 'Verify system configuration',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
    gradient: 'from-blue-500 to-cyan-500',
    shadowColor: 'shadow-blue-500/20',
    accentColor: 'text-blue-600',
    bgGradient: 'bg-gradient-to-br from-blue-50 to-cyan-50',
  },
  {
    id: 'gateway-diagnosis',
    title: 'Gateway Diagnostics',
    description: 'Diagnose gateway connection status',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
    gradient: 'from-purple-500 to-pink-500',
    shadowColor: 'shadow-purple-500/20',
    accentColor: 'text-purple-600',
    bgGradient: 'bg-gradient-to-br from-purple-50 to-pink-50',
  },
  {
    id: 'env-detection',
    title: 'Environment Detection',
    description: 'Detect runtime environment',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
      </svg>
    ),
    gradient: 'from-cyan-500 to-blue-500',
    shadowColor: 'shadow-cyan-500/20',
    accentColor: 'text-cyan-600',
    bgGradient: 'bg-gradient-to-br from-cyan-50 to-blue-50',
  },
  {
    id: 'one-click-fix',
    title: 'Quick Fix',
    description: 'Auto-fix common issues',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z" />
      </svg>
    ),
    gradient: 'from-emerald-500 to-teal-500',
    shadowColor: 'shadow-emerald-500/20',
    accentColor: 'text-emerald-600',
    bgGradient: 'bg-gradient-to-br from-emerald-50 to-teal-50',
  },
  {
    id: 'system-info',
    title: 'System Info',
    description: 'View detailed system information',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
      </svg>
    ),
    gradient: 'from-orange-500 to-amber-500',
    shadowColor: 'shadow-orange-500/20',
    accentColor: 'text-orange-600',
    bgGradient: 'bg-gradient-to-br from-orange-50 to-amber-50',
  },
  {
    id: 'log-viewer',
    title: 'Log Viewer',
    description: 'View system runtime logs',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
    gradient: 'from-pink-500 to-rose-500',
    shadowColor: 'shadow-pink-500/20',
    accentColor: 'text-pink-600',
    bgGradient: 'bg-gradient-to-br from-pink-50 to-rose-50',
  },
  {
    id: 'memory-manager',
    title: 'Memory Manager',
    description: 'Manage AI memory storage',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
      </svg>
    ),
    gradient: 'from-indigo-500 to-violet-500',
    shadowColor: 'shadow-indigo-500/20',
    accentColor: 'text-indigo-600',
    bgGradient: 'bg-gradient-to-br from-indigo-50 to-violet-50',
  },
  {
    id: 'quick-settings',
    title: 'Quick Settings',
    description: 'Quick configuration options',
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    gradient: 'from-teal-500 to-cyan-500',
    shadowColor: 'shadow-teal-500/20',
    accentColor: 'text-teal-600',
    bgGradient: 'bg-gradient-to-br from-teal-50 to-cyan-50',
  },
];

const CHANNEL_ICONS: Record<string, React.ReactNode> = {
  whatsapp: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
    </svg>
  ),
  telegram: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
    </svg>
  ),
  discord: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z"/>
    </svg>
  ),
  slack: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312zM15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z"/>
    </svg>
  ),
  wechat: (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1-.023-.156.49.49 0 0 1 .201-.398C23.024 18.48 24 16.82 24 14.98c0-3.21-2.931-5.837-6.656-6.088V8.89c-.135-.01-.27-.027-.407-.03zm-2.53 3.274c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982z"/>
    </svg>
  ),
  default: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
    </svg>
  ),
};

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  system: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
    </svg>
  ),
  channel: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
    </svg>
  ),
  task: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  agent: (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
    </svg>
  ),
};

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  
  return parts.join(' ') || '0m';
};

const formatBytes = (bytes: number): string => {
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${Math.round(mb)} MB`;
};

const getProgressColor = (percent: number): string => {
  if (percent < 50) {
    return 'from-accent-emerald to-accent-teal';
  } else if (percent <= 80) {
    return 'from-accent-yellow to-accent-orange';
  } else {
    return 'from-accent-red to-accent-orange';
  }
};

const computeChannelCounts = (items: DashboardChannelSummary[]) => ({
  total: items.length,
  enabled: items.filter((item) => item.enabled).length,
  online: items.filter((item) => item.status === 'online').length,
  disabled: items.filter((item) => item.status === 'disabled').length,
  misconfigured: items.filter((item) => item.status === 'error').length,
});

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [channelLoading, setChannelLoading] = useState<string | null>(null);
  const [channelError, setChannelError] = useState<string | null>(null);
  const [copiedVersion, setCopiedVersion] = useState(false);

  const [activeModal, setActiveModal] = useState<string | null>(null);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [configCheckData, setConfigCheckData] = useState<ConfigCheckResultData | null>(null);
  const [gatewayDiagnosticsData, setGatewayDiagnosticsData] = useState<GatewayDiagnosticsData | null>(null);
  const [environmentData, setEnvironmentData] = useState<EnvironmentDetectionData | null>(null);
  const [memoryData, setMemoryData] = useState<MemoryData | null>(null);
  const [fixLoading, setFixLoading] = useState(false);
  const [showFixConfirm, setShowFixConfirm] = useState(false);
  const [fixResult, setFixResult] = useState<{
    fixed: Array<{ issue: string; message: string }>;
    failed: Array<{ issue: string; error: string }>;
    suggestions: Array<{ issue: string; message: string; action: string }>;
  } | null>(null);

  useEffect(() => {
    let disposed = false;
    let hasLoadedInitial = false;

    const fetchData = async (silent: boolean = false) => {
      if (!silent) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const summaryData = await statusService.getDashboardSummary();
        if (disposed) {
          return;
        }
        setDashboardSummary(summaryData);
        hasLoadedInitial = true;
      } catch (err) {
        if (!disposed && !hasLoadedInitial) {
          setError('Failed to load data');
        }
        console.error('Error fetching dashboard data:', err);
      } finally {
        if (!disposed && !silent) {
          setIsLoading(false);
        }
      }
    };

    void fetchData();
    const intervalId = window.setInterval(() => {
      void fetchData(true);
    }, 30000);

    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, []);

  const handleSkillClick = async (skillId: string) => {
    switch (skillId) {
      case 'config-check':
        setActiveModal('config-check');
        setModalLoading(true);
        setModalError(null);
        setConfigCheckData(null);
        try {
          const data = await diagnosticsService.validateConfig();
          setConfigCheckData(data);
        } catch (err) {
          setModalError(err instanceof Error ? err.message : '配置检查失败');
        } finally {
          setModalLoading(false);
        }
        break;

      case 'gateway-diagnosis':
        setActiveModal('gateway-diagnosis');
        setModalLoading(true);
        setModalError(null);
        setGatewayDiagnosticsData(null);
        try {
          const data = await diagnosticsService.getGatewayDiagnostics();
          setGatewayDiagnosticsData(data);
        } catch (err) {
          setModalError(err instanceof Error ? err.message : '网关诊断失败');
        } finally {
          setModalLoading(false);
        }
        break;

      case 'env-detection':
        setActiveModal('env-detection');
        setModalLoading(true);
        setModalError(null);
        setEnvironmentData(null);
        try {
          const data = await diagnosticsService.getEnvironment();
          setEnvironmentData(data);
        } catch (err) {
          setModalError(err instanceof Error ? err.message : '环境检测失败');
        } finally {
          setModalLoading(false);
        }
        break;

      case 'one-click-fix':
        setShowFixConfirm(true);
        break;

      case 'memory-manager':
        setActiveModal('memory-manager');
        setModalLoading(true);
        setModalError(null);
        setMemoryData(null);
        try {
          const data = await diagnosticsService.getMemory();
          setMemoryData(data);
        } catch (err) {
          setModalError(err instanceof Error ? err.message : '获取内存信息失败');
        } finally {
          setModalLoading(false);
        }
        break;

      case 'system-info':
        navigate('/status');
        break;

      case 'log-viewer':
        navigate('/status', { state: { activeTab: 'logs' } });
        break;

      case 'quick-settings':
        navigate('/config');
        break;

      default:
        console.log('Unknown skill:', skillId);
    }
  };

  const handleCloseModal = () => {
    setActiveModal(null);
    setModalError(null);
  };

  const handleConfirmFix = async () => {
    setFixLoading(true);
    setFixResult(null);
    try {
      const result = await diagnosticsService.runFix();
      setFixResult(result);
      setShowFixConfirm(false);
      setActiveModal('fix-result');
    } catch (err) {
      alert(err instanceof Error ? err.message : '一键修复失败');
    } finally {
      setFixLoading(false);
    }
  };

  const handleCancelFix = () => {
    setShowFixConfirm(false);
  };

  const handleToggleChannel = async (channelName: string, enabled: boolean) => {
    setChannelLoading(channelName);
    setChannelError(null);
    
    try {
      await channelsService.updateChannel(channelName, { enabled });

      setDashboardSummary((prev) => {
        if (!prev) {
          return prev;
        }

        const items: DashboardChannelSummary[] = prev.channels.items.map((item) => {
          if (item.name !== channelName) {
            return item;
          }

          const nextStatus: DashboardChannelSummary['status'] = enabled
            ? (item.configured ? 'online' : 'error')
            : 'disabled';

          return {
            ...item,
            enabled,
            status: nextStatus,
            status_label: enabled ? (item.configured ? '就绪' : '配置缺失') : '已禁用',
            reason: enabled
              ? (item.configured ? null : item.reason || '缺少必要配置')
              : '当前通道未启用',
          };
        });

        return {
          ...prev,
          channels: {
            ...prev.channels,
            items,
            counts: computeChannelCounts(items),
          },
        };
      });
    } catch (err) {
      console.error('Error toggling channel:', err);
      setChannelError(`切换通道 ${channelName} 失败`);
      setTimeout(() => setChannelError(null), 3000);
    } finally {
      setChannelLoading(null);
    }
  };

  const systemStatus: SystemStatus | null = dashboardSummary?.system_status ?? null;
  const channelStatusList = dashboardSummary?.channels.items ?? [];
  const recentActivities = dashboardSummary?.recent_activities ?? [];
  const dashboardAlerts = dashboardSummary?.alerts ?? [];

  const handleCopyVersion = async () => {
    if (!systemStatus?.version) return;
    
    try {
      await navigator.clipboard.writeText(systemStatus.version);
      setCopiedVersion(true);
      setTimeout(() => setCopiedVersion(false), 2000);
    } catch (err) {
      console.error('Failed to copy version:', err);
    }
  };

  if (isLoading) {
    return (
      <div className="h-full overflow-y-auto bg-surface-100">
        <div className="max-w-7xl mx-auto p-8 space-y-8">
          <Skeleton variant="text" height="40px" width="200px" />
          <Skeleton variant="text" height="24px" width="300px" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full overflow-y-auto bg-surface-100">
        <div className="max-w-7xl mx-auto p-8">
          <div className="flex flex-col items-center justify-center min-h-[400px]">
            <div className="w-20 h-20 rounded-2xl bg-accent-red/10 flex items-center justify-center mb-6">
              <svg className="w-10 h-10 text-accent-red" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
            </div>
            <h2 className="text-2xl font-semibold text-surface-900 mb-3">加载失败</h2>
            <p className="text-surface-600 mb-6">{error}</p>
            <button onClick={() => window.location.reload()} className="btn btn-primary">
              重试
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-gradient-to-br from-surface-50 via-surface-100 to-surface-50">
      <div className="max-w-7xl mx-auto p-8 space-y-6">
        {/* 顶部区域 - 带渐变背景 */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-primary-600 via-primary-500 to-accent-indigo p-8 shadow-lg shadow-primary-500/20 -mx-8 px-8 mb-6">
          {/* 装饰性背景 */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />
          <div className="absolute top-1/2 right-1/4 w-32 h-32 bg-white/5 rounded-full" />
          
          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center shadow-lg overflow-hidden">
                  <img src="/logo.png" alt="Logo" className="w-14 h-14 object-contain" />
                </div>
                <div>
                  <h1 className="text-[32px] font-bold text-white tracking-tight">Dashboard</h1>
                  <p className="text-white/70 text-sm mt-1">horbot Dashboard</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {systemStatus?.status === 'running' ? (
                <div className="inline-flex items-center justify-center gap-2.5 px-6 py-3 bg-white/20 backdrop-blur-sm rounded-full text-white font-medium text-sm shadow-lg border border-white/20 transition-all duration-300 hover:bg-white/30 hover:shadow-xl">
                  <div className="relative flex items-center justify-center">
                    <div className="w-3 h-3 bg-white rounded-full animate-ping opacity-75"></div>
                    <div className="absolute inset-0 w-3 h-3 bg-white rounded-full"></div>
                  </div>
                  <span className="tracking-wide">Running</span>
                  <span className="text-xs text-white/70 ml-1">• {systemStatus ? formatUptime(systemStatus.uptime_seconds) : ''}</span>
                </div>
              ) : (
                <div className="inline-flex items-center justify-center gap-2.5 px-6 py-3 bg-gradient-to-r from-accent-red to-accent-orange rounded-full text-white font-medium text-sm shadow-lg shadow-accent-red/20 transition-all duration-300 hover:shadow-xl hover:shadow-accent-red/30 border border-white/20">
                  <div className="flex items-center justify-center">
                    <div className="w-3 h-3 bg-white rounded-full"></div>
                  </div>
                  <span className="tracking-wide">Stopped</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {dashboardAlerts.length > 0 && (
          <div className="grid gap-3 md:grid-cols-2">
            {dashboardAlerts.slice(0, 4).map((alert) => (
              <div
                key={alert.id}
                data-testid={`dashboard-alert-${alert.id}`}
                className={`rounded-2xl border px-4 py-3 shadow-sm ${
                  alert.level === 'error'
                    ? 'border-red-200 bg-red-50'
                    : alert.level === 'warning'
                      ? 'border-amber-200 bg-amber-50'
                      : 'border-sky-200 bg-sky-50'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-0.5 h-2.5 w-2.5 rounded-full ${
                    alert.level === 'error'
                      ? 'bg-red-500'
                      : alert.level === 'warning'
                        ? 'bg-amber-500'
                        : 'bg-sky-500'
                  }`} />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-surface-900">{alert.title}</p>
                    <p className="mt-1 text-sm text-surface-600">{alert.message}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div>
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-surface-900 tracking-tight">AI Assistant Skills</h2>
              <p className="text-sm text-surface-500 mt-1.5 font-light">Quick access to common features</p>
            </div>
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-surface-100 rounded-full">
              <span className="w-2 h-2 rounded-full bg-primary-500 animate-pulse"></span>
              <span className="text-xs font-medium text-surface-600">{AI_SKILLS.length} 项可用</span>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {AI_SKILLS.map((skill, index) => (
              <div
                key={skill.id}
                onClick={() => handleSkillClick(skill.id)}
                className={`
                  relative overflow-hidden
                  bg-white border border-surface-200/80 rounded-2xl p-5
                  cursor-pointer transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]
                  hover:shadow-xl hover:-translate-y-2 hover:border-transparent
                  group
                  active:scale-[0.98] active:transition-all active:duration-150
                `}
                style={{ 
                  animationDelay: `${index * 60}ms`,
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)'
                }}
              >
                {/* 悬浮层光晕效果 */}
                <div className={`absolute inset-0 bg-gradient-to-br ${skill.gradient} opacity-0 group-hover:opacity-100 transition-all duration-500 ease-out`} style={{ mixBlendMode: 'overlay' }} />
                
                {/* 悬停时的渐变边框效果 */}
                <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${skill.gradient} opacity-0 group-hover:opacity-15 transition-opacity duration-500 -z-10`} style={{ margin: '-1px' }} />
                
                {/* 动态背景圆点 */}
                <div className={`absolute -top-8 -right-8 w-24 h-24 bg-gradient-to-br ${skill.gradient} opacity-0 group-hover:opacity-10 transition-all duration-700 ease-out rounded-full blur-2xl transform group-hover:scale-150`} />
                
                <div className={`relative w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-all duration-500 ease-out group-hover:scale-110 group-hover:shadow-lg ${skill.shadowColor} bg-gradient-to-br ${skill.gradient}`}>
                  <div className="text-white drop-shadow-sm">
                    {skill.icon}
                  </div>
                  {/* 悬浮时的光晕 */}
                  <div className={`absolute inset-0 rounded-xl bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-md`} />
                </div>
                
                <div className="relative">
                  <h3 className="text-[15px] font-semibold text-surface-900 mb-1.5 tracking-tight group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-surface-900 group-hover:to-surface-700 transition-all duration-300">{skill.title}</h3>
                  <p className="text-[13px] text-surface-500 leading-relaxed group-hover:text-surface-600 transition-colors duration-300">{skill.description}</p>
                </div>
                
                {/* 箭头指示器 - 更精致的动画 */}
                <div className="absolute top-5 right-5 opacity-0 group-hover:opacity-100 transform translate-x-3 group-hover:translate-x-0 transition-all duration-400 ease-out">
                  <div className={`w-8 h-8 rounded-full bg-gradient-to-br ${skill.gradient} flex items-center justify-center shadow-lg group-hover:shadow-xl transition-shadow duration-300`}>
                    <svg className="w-4 h-4 text-white transform group-hover:translate-x-0.5 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                    </svg>
                  </div>
                </div>
                
                {/* 点击波纹效果 */}
                <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
                  <div className="absolute inset-0 bg-gradient-to-br from-white/30 to-transparent opacity-0 group-active:opacity-100 transition-opacity duration-150" />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mt-2">
          <div data-testid="dashboard-system-status-card" className="xl:col-span-1 bg-white rounded-2xl shadow-sm border border-surface-200/60 overflow-hidden">
            <div className="p-3">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary-500 to-accent-indigo flex items-center justify-center shadow-sm">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-base font-semibold text-surface-900 tracking-tight">System Status</h3>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-surface-600">Status</span>
                  <Badge variant={systemStatus?.status === 'running' ? 'success' : 'error'} size="sm" dot>
                    {systemStatus?.status === 'running' ? 'Running' : 'Stopped'}
                  </Badge>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-surface-600">CPU Usage</span>
                    <span className="text-sm font-medium text-surface-900">{systemStatus ? `${systemStatus.system.cpu_percent.toFixed(1)}%` : 'N/A'}</span>
                  </div>
                  <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full bg-gradient-to-r ${getProgressColor(systemStatus?.system.cpu_percent || 0)} rounded-full transition-all duration-700 ease-out`} 
                      style={{ width: `${Math.min(systemStatus?.system.cpu_percent || 0, 100)}%` }} 
                    />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-surface-600">Memory Usage</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-surface-900">{systemStatus ? `${Math.round(systemStatus.system.memory.percent)}%` : 'N/A'}</span>
                      {systemStatus && systemStatus.system.memory.percent > 80 && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-semantic-warning-light text-semantic-warning">
                          High
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
                    <div 
                      className={`h-full bg-gradient-to-r ${getProgressColor(systemStatus?.system.memory.percent || 0)} rounded-full transition-all duration-700 ease-out`} 
                      style={{ width: `${Math.min(systemStatus?.system.memory.percent || 0, 100)}%` }} 
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-surface-100">
                  <span className="text-sm text-surface-600">Uptime</span>
                  <span className="text-sm font-medium text-surface-900">{systemStatus ? formatUptime(systemStatus.uptime_seconds) : 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>

          <Card data-testid="dashboard-activity-card" className="xl:col-span-2 border border-surface-200/60 shadow-sm hover:shadow-lg transition-shadow duration-500 ease-out overflow-hidden">
            <CardHeader 
              className="mb-4 px-5 pt-5"
              title={
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-surface-900 tracking-tight">Recent Activity</span>
                  <span className="px-2 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full shadow-sm">
                    {recentActivities.length}
                  </span>
                </div>
              } 
              action={<Link to="/status" className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1.5 group">
                View More
                <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
              </Link>} 
            />
            <CardContent padding="none">
              {recentActivities.length > 0 ? (
                <div className="divide-y divide-surface-100/80">
                  {recentActivities.map((activity, index) => (
                    <div 
                      key={activity.id} 
                      data-testid={`dashboard-activity-${activity.id}`}
                      className="flex items-start gap-4 px-5 py-4 hover:bg-gradient-to-r hover:from-surface-50/80 hover:to-transparent transition-all duration-300 ease-out group"
                      style={{ animationDelay: `${index * 80}ms` }}
                    >
                      <div className={`relative w-10 h-10 rounded-[10px] flex items-center justify-center flex-shrink-0 transition-all duration-300 group-hover:scale-110 ${
                        activity.status === 'success' ? 'bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 shadow-sm' :
                        activity.status === 'warning' ? 'bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 shadow-sm' :
                        activity.status === 'error' ? 'bg-gradient-to-br from-red-100 to-red-50 text-red-600 shadow-sm' :
                        'bg-gradient-to-br from-primary-100 to-primary-50 text-primary-600 shadow-sm'
                      }`}>
                        {ACTIVITY_ICONS[activity.type]}
                        {/* 状态指示灯 */}
                        <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white flex items-center justify-center ${
                          activity.status === 'success' ? 'bg-emerald-500' :
                          activity.status === 'warning' ? 'bg-amber-500' :
                          activity.status === 'error' ? 'bg-red-500' : 'bg-primary-500'
                        }`}>
                          <div className="w-1 h-1 rounded-full bg-white animate-pulse" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[14px] font-medium text-surface-900 tracking-wide">{activity.message}</p>
                        <div className="flex items-center gap-3 mt-1.5">
                          <p className="text-[12px] text-surface-400 flex items-center gap-1.5 group-hover:text-surface-500 transition-colors duration-300">
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            {activity.time}
                          </p>
                          <Badge 
                            variant={
                              activity.status === 'success'
                                ? 'success'
                                : activity.status === 'error'
                                  ? 'error'
                                  : 'info'
                            } 
                            size="sm"
                            className="text-[10px] px-2 py-0.5 font-medium"
                          >
                            {activity.status === 'success' ? (
                              <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>Success</>
                            ) : activity.status === 'warning' ? (
                              <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l6.518 11.595c.75 1.334-.213 2.996-1.742 2.996H3.48c-1.53 0-2.492-1.662-1.742-2.996L8.257 3.1zM11 8a1 1 0 10-2 0v3a1 1 0 102 0V8zm-1 7a1.25 1.25 0 100-2.5A1.25 1.25 0 0010 15z" clipRule="evenodd" /></svg>Warning</>
                            ) : activity.status === 'error' ? (
                              <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" /></svg>Failed</>
                            ) : (
                              <><svg className="w-2.5 h-2.5 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" /></svg>Info</>
                            )}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-14 px-6">
                  <div className="relative mb-4">
                    <div className="w-24 h-24 rounded-full bg-surface-100 flex items-center justify-center">
                      <svg className="w-12 h-12 text-surface-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                      </svg>
                    </div>
                    <div className="absolute inset-0 w-24 h-24 rounded-full bg-primary-100/50 animate-pulse opacity-0" />
                  </div>
                  <p className="text-surface-600 font-medium text-center">No recent activity</p>
                  <p className="text-surface-400 text-sm text-center mt-1">Activity records will appear after system starts</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 gap-6 mt-6">
          <Card data-testid="dashboard-channel-card" className="border border-surface-200/60 shadow-sm hover:shadow-lg transition-all duration-500 ease-out overflow-hidden">
            <CardHeader 
              title={
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-surface-900 tracking-tight">Channel Status</span>
                  <span className="px-2.5 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-700 rounded-full shadow-sm flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    {dashboardSummary?.channels.counts.online ?? 0} Online
                  </span>
                </div>
              } 
              action={<Link to="/channels" className="text-sm font-medium text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1.5 group">
                Manage
                <svg className="w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
              </Link>} 
            />
            <CardContent padding="none">
              {channelError && (
                <div className="mx-5 mt-4 p-3.5 bg-red-50 border border-red-100 rounded-xl animate-shake shadow-sm">
                  <p className="text-sm text-red-600 flex items-center gap-2.5">
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                    </svg>
                    {channelError}
                  </p>
                </div>
              )}
              {channelStatusList.length > 0 ? (
                <div className="divide-y divide-surface-100/80">
                  {channelStatusList.map((channel) => {
                    const channelKey = channel.name.toLowerCase();
                    const channelIcon = CHANNEL_ICONS[channelKey] || CHANNEL_ICONS.default;
                    const isLoading = channelLoading === channel.name;
                    
                    return (
                      <div key={channel.name} data-testid={`dashboard-channel-${channel.name}`} className="flex items-center justify-between px-5 py-3.5 hover:bg-gradient-to-r hover:from-surface-50/80 hover:to-transparent transition-all duration-300 group">
                        <div className="flex items-center gap-3.5">
                          <div className={`relative w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 group-hover:scale-105 ${
                            channel.status === 'online' 
                              ? 'bg-gradient-to-br from-emerald-100 to-emerald-50 text-emerald-600 shadow-md shadow-emerald-500/10' 
                              : channel.status === 'error'
                                ? 'bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 shadow-sm'
                              : 'bg-surface-100 text-surface-400 shadow-sm'
                          }`}>
                            {channelIcon}
                            {/* 在线状态指示点 */}
                            {channel.status === 'online' && (
                              <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-white rounded-full flex items-center justify-center shadow-sm">
                                <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-lg shadow-emerald-500/50 animate-pulse" />
                              </div>
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2.5">
                              <span className="font-medium text-surface-900 tracking-wide">{channel.display_name}</span>
                              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                channel.status === 'online'
                                  ? 'bg-emerald-50 text-emerald-600'
                                  : channel.status === 'error'
                                    ? 'bg-amber-50 text-amber-700'
                                    : 'bg-surface-100 text-surface-500'
                              }`}>
                                {channel.status_label}
                              </span>
                            </div>
                            {channel.reason && (
                              <p className="mt-1 text-xs text-surface-500">{channel.reason}</p>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={() => handleToggleChannel(channel.name, !channel.enabled)}
                          disabled={isLoading}
                          className={`relative inline-flex h-7 w-12 items-center rounded-full transition-all duration-500 ease-out ${
                            channel.enabled 
                              ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 shadow-lg shadow-emerald-500/30' 
                              : 'bg-surface-200 hover:bg-surface-300'
                          } ${isLoading ? 'opacity-70 cursor-not-allowed' : 'hover:scale-105 active:scale-95'}`}
                        >
                          {isLoading ? (
                            <span className="inline-block h-4 w-4 mx-auto rounded-full bg-white flex items-center justify-center">
                              <svg className="w-3 h-3 animate-spin text-emerald-500" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                              </svg>
                            </span>
                          ) : (
                            <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-transform duration-500 ease-[cubic-bezier(0.68,-0.55,0.265,1.55)] ${
                              channel.enabled ? 'translate-x-6' : 'translate-x-1'
                            }`}>
                              <div className={`absolute inset-0.5 rounded-full ${channel.enabled ? 'bg-emerald-400' : 'bg-surface-400'} transition-colors duration-300`} />
                            </span>
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-10 text-center">
                  <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-surface-100 flex items-center justify-center">
                    <svg className="w-8 h-8 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                    </svg>
                  </div>
                  <p className="text-surface-500 font-medium">No enabled channels</p>
                  <p className="text-surface-400 text-sm mt-1">Add and enable channels in the Channels page</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card data-testid="dashboard-system-info-card" className="border border-surface-200/60 shadow-sm hover:shadow-lg transition-all duration-500 ease-out overflow-hidden">
            <CardHeader 
              title={
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-surface-900 tracking-tight">System Information</span>
                  <span className="px-2.5 py-0.5 text-xs font-medium bg-primary-100 text-primary-700 rounded-full shadow-sm">
                    v{systemStatus?.version?.split('.')[0] || '0'}
                  </span>
                </div>
              } 
            />
            <CardContent>
              <div className="space-y-1 p-2">
                <div className="flex items-center justify-between py-3 px-3 rounded-xl hover:bg-surface-50 transition-all duration-300 group cursor-pointer" onClick={handleCopyVersion}>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary-100 to-primary-50 text-primary-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow duration-300">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                    </div>
                    <div>
                      <span className="text-sm text-surface-600 block">Version</span>
                      <span className="text-xs text-surface-400">Version</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 group-hover:gap-3 transition-all duration-300">
                    <span className="text-sm font-mono font-medium text-surface-900 bg-surface-100 px-3 py-1.5 rounded-lg">{systemStatus?.version || 'N/A'}</span>
                    {copiedVersion ? (
                      <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 animate-bounce">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    ) : (
                      <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-100 text-surface-400 hover:bg-primary-50 hover:text-primary-600 opacity-0 group-hover:opacity-100 transition-all duration-300">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between py-3 px-3 rounded-xl hover:bg-surface-50 transition-all duration-300 group">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-purple-100 to-purple-50 text-purple-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow duration-300">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-3 2.148 2.148A12.061 12.061 0 0116.5 7.605" />
                      </svg>
                    </div>
                    <div>
                      <span className="text-sm text-surface-600 block">Memory Usage</span>
                      <span className="text-xs text-surface-400">Memory Usage</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="text-right">
                      <span className="text-sm font-mono font-medium text-surface-900 block">{systemStatus ? `${formatBytes(systemStatus.system.memory.used)}` : 'N/A'}</span>
                      <span className="text-xs text-surface-400">/ {systemStatus ? `${formatBytes(systemStatus.system.memory.total)}` : 'N/A'}</span>
                    </div>
                    <div className="w-16 h-2 bg-surface-100 rounded-full overflow-hidden">
                      <div 
                        className={`h-full bg-gradient-to-r ${getProgressColor(systemStatus?.system.memory.percent || 0)} rounded-full transition-all duration-700`}
                        style={{ width: `${systemStatus?.system.memory.percent || 0}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between py-3 px-3 rounded-xl hover:bg-surface-50 transition-all duration-300 group">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-100 to-amber-50 text-amber-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow duration-300">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
                      </svg>
                    </div>
                    <div>
                      <span className="text-sm text-surface-600 block">Disk Usage</span>
                      <span className="text-xs text-surface-400">Disk Usage</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-mono font-medium text-surface-900">{systemStatus?.system.disk ? `${Math.round(systemStatus.system.disk.percent)}%` : 'N/A'}</span>
                    <div className="w-16 h-2 bg-surface-100 rounded-full overflow-hidden">
                      <div 
                        className={`h-full bg-gradient-to-r ${systemStatus?.system.disk && systemStatus.system.disk.percent > 80 ? 'from-amber-500 to-red-500' : 'from-amber-500 to-orange-500'} rounded-full transition-all duration-700`}
                        style={{ width: `${systemStatus?.system.disk?.percent || 0}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <DiagnosticModal
        title="配置检查"
        isOpen={activeModal === 'config-check'}
        onClose={handleCloseModal}
        isLoading={modalLoading}
        error={modalError}
        size="xl"
      >
        {configCheckData && <ConfigCheckResult data={configCheckData} />}
      </DiagnosticModal>

      <DiagnosticModal
        title="网关诊断"
        isOpen={activeModal === 'gateway-diagnosis'}
        onClose={handleCloseModal}
        isLoading={modalLoading}
        error={modalError}
        size="xl"
      >
        {gatewayDiagnosticsData && <GatewayDiagnosticsResult data={gatewayDiagnosticsData} />}
      </DiagnosticModal>

      <DiagnosticModal
        title="环境检测"
        isOpen={activeModal === 'env-detection'}
        onClose={handleCloseModal}
        isLoading={modalLoading}
        error={modalError}
        size="full"
      >
        {environmentData && <EnvironmentDetectionResult data={environmentData} />}
      </DiagnosticModal>

      <DiagnosticModal
        title="内存管理"
        isOpen={activeModal === 'memory-manager'}
        onClose={handleCloseModal}
        isLoading={modalLoading}
        error={modalError}
        size="lg"
      >
        {memoryData && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                <p className="text-sm text-surface-600">总条目数</p>
                <p className="text-2xl font-bold text-surface-900">{memoryData.total_entries}</p>
              </div>
              <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                <p className="text-sm text-surface-600">总大小</p>
                <p className="text-2xl font-bold text-surface-900">{memoryData.total_size_kb.toFixed(2)} KB</p>
              </div>
            </div>
            {memoryData.oldest_entry && memoryData.newest_entry && (
              <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                <h4 className="text-sm font-semibold text-surface-700 mb-3">时间范围</h4>
                <div className="flex justify-between text-sm">
                  <span className="text-surface-600">最早条目:</span>
                  <span className="text-surface-800">{new Date(memoryData.oldest_entry).toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm mt-2">
                  <span className="text-surface-600">最新条目:</span>
                  <span className="text-surface-800">{new Date(memoryData.newest_entry).toLocaleString()}</span>
                </div>
              </div>
            )}
            {memoryData.details && (
              <div className="bg-surface-50 rounded-xl p-4 border border-surface-200">
                <h4 className="text-sm font-semibold text-surface-700 mb-3">详细信息</h4>
                <pre className="text-xs text-surface-600 overflow-auto max-h-40">
                  {JSON.stringify(memoryData.details, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </DiagnosticModal>

      <ConfirmDialog
        isOpen={showFixConfirm}
        title="一键修复"
        message="确定要执行一键修复吗？此操作将自动修复检测到的常见问题。"
        confirmText="执行修复"
        cancelText="取消"
        onConfirm={handleConfirmFix}
        onCancel={handleCancelFix}
        variant="warning"
        isLoading={fixLoading}
      />

      <DiagnosticModal
        title="修复结果"
        isOpen={activeModal === 'fix-result'}
        onClose={handleCloseModal}
        size="lg"
      >
        {fixResult && (
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
        )}
      </DiagnosticModal>
    </div>
  );
};

export default DashboardPage;
