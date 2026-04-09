import React, { useState, useEffect } from 'react';
import { tasksService } from '../services';
import { useToast } from '../contexts/ToastContext';
import { Card, CardContent, Button, Badge, Modal, Input } from '../components/ui';
import { formatRelativeTime, formatAbsoluteTime } from '../utils/date';
import type { Task, TaskSchedule, DeliveryTarget } from '../types';

const TasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState<'all' | 'enabled' | 'disabled'>('all');
  const [runningTasks, setRunningTasks] = useState<Set<string>>(new Set());
  const { success: showSuccess, error: showError } = useToast();
  const [newTask, setNewTask] = useState({
    name: '',
    scheduleKind: 'every' as 'every' | 'cron',
    everyMs: 3600000,
    expr: '',
    message: '',
    deliver: false,
    channels: [] as DeliveryTarget[],
  });

  const fetchTasks = async () => {
    try {
      const response = await tasksService.getTasks();
      setTasks(response || []);
      setError(null);
    } catch (err) {
      setError('Failed to fetch tasks');
      console.error('Error fetching tasks:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleDeleteTask = async (taskId: string, taskName: string) => {
    if (!confirm(`Are you sure you want to delete task "${taskName}"?`)) return;
    
    try {
      await tasksService.deleteTask(taskId);
      await fetchTasks();
      showSuccess(`Task "${taskName}" deleted`);
    } catch (err) {
      showError('Failed to delete task');
      console.error('Error deleting task:', err);
    }
  };

  const handleToggleTask = async (taskId: string, enabled: boolean, taskName: string) => {
    try {
      await tasksService.toggleTask(taskId, enabled);
      await fetchTasks();
      showSuccess(`Task "${taskName}" ${!enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      showError('Failed to toggle task status');
      console.error('Error toggling task:', err);
    }
  };

  const handleRunTask = async (taskId: string, taskName: string) => {
    // Mark task as running
    setRunningTasks(prev => new Set(prev).add(taskId));
    
    try {
      await tasksService.runTask(taskId);
      showSuccess(`Task "${taskName}" started executing...`);
      
      // Poll for task completion (check every 2 seconds for up to 60 seconds)
      let attempts = 0;
      const maxAttempts = 30;
      const pollInterval = setInterval(async () => {
        attempts++;
        
        try {
          const response = await tasksService.getTasks();
          const task = response?.find(t => t.id === taskId);
          
          if (task && task.state.last_run_at_ms) {
            // Task has completed
            clearInterval(pollInterval);
            setRunningTasks(prev => {
              const next = new Set(prev);
              next.delete(taskId);
              return next;
            });
            
            await fetchTasks();
            
            if (task.state.last_status === 'ok') {
              showSuccess(`Task "${taskName}" completed successfully`);
            } else if (task.state.last_status === 'error') {
              showError(`Task "${taskName}" failed: ${task.state.last_error || 'Unknown error'}`);
            }
          }
          
          if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            setRunningTasks(prev => {
              const next = new Set(prev);
              next.delete(taskId);
              return next;
            });
            showSuccess(`Task "${taskName}" is still running. Check back later for results.`);
          }
        } catch (err) {
          console.error('Error polling task status:', err);
        }
      }, 2000);
      
    } catch (err) {
      setRunningTasks(prev => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
      showError('Failed to run task');
      console.error('Error running task:', err);
    }
  };

  const handleAddTask = async () => {
    if (!newTask.name || !newTask.message) {
      showError('Name and message are required');
      return;
    }

    try {
      const schedule: TaskSchedule = { kind: newTask.scheduleKind };
      if (newTask.scheduleKind === 'every') {
        schedule.every_ms = newTask.everyMs;
      } else if (newTask.scheduleKind === 'cron') {
        schedule.expr = newTask.expr;
      }

      const taskData = {
        name: newTask.name,
        schedule,
        message: newTask.message,
        deliver: newTask.deliver,
        channels: newTask.channels.length > 0 ? newTask.channels : undefined,
      };

      await tasksService.createTask(taskData);
      setShowAddModal(false);
      setNewTask({
        name: '',
        scheduleKind: 'every',
        everyMs: 3600000,
        expr: '',
        message: '',
        deliver: false,
        channels: [],
      });
      await fetchTasks();
      showSuccess(`Task "${newTask.name}" created successfully`);
    } catch (err) {
      showError('Failed to add task');
      console.error('Error adding task:', err);
    }
  };

  const handleAddChannel = () => {
    setNewTask({
      ...newTask,
      channels: [...newTask.channels, { channel: '', to: '' }]
    });
  };

  const handleRemoveChannel = (index: number) => {
    setNewTask({
      ...newTask,
      channels: newTask.channels.filter((_, i) => i !== index)
    });
  };

  const handleUpdateChannel = (index: number, field: 'channel' | 'to', value: string) => {
    const updatedChannels = [...newTask.channels];
    updatedChannels[index] = { ...updatedChannels[index], [field]: value };
    setNewTask({ ...newTask, channels: updatedChannels });
  };

  const handleEditTask = (task: Task) => {
    setEditingTask(task);
    const scheduleKind = task.schedule.kind as 'every' | 'cron';
    const channels = task.payload.channels || 
      (task.payload.channel && task.payload.to ? [{ channel: task.payload.channel, to: task.payload.to }] : []);
    
    setNewTask({
      name: task.name,
      scheduleKind,
      everyMs: task.schedule.every_ms || 3600000,
      expr: task.schedule.expr || '',
      message: task.payload.message,
      deliver: task.payload.deliver,
      channels,
    });
    setShowAddModal(true);
  };

  const handleUpdateTask = async () => {
    if (!editingTask || !newTask.name || !newTask.message) {
      showError('Name and message are required');
      return;
    }

    try {
      const schedule: TaskSchedule = { kind: newTask.scheduleKind };
      if (newTask.scheduleKind === 'every') {
        schedule.every_ms = newTask.everyMs;
      } else if (newTask.scheduleKind === 'cron') {
        schedule.expr = newTask.expr;
      }

      const taskData = {
        name: newTask.name,
        schedule,
        payload: {
          kind: 'agent_turn',
          message: newTask.message,
          deliver: newTask.deliver,
          channels: newTask.channels.length > 0 ? newTask.channels : undefined,
          notify: editingTask.payload.notify ?? false,
        },
      };

      await tasksService.updateTask(editingTask.id, taskData);
      setShowAddModal(false);
      setEditingTask(null);
      setNewTask({
        name: '',
        scheduleKind: 'every',
        everyMs: 3600000,
        expr: '',
        message: '',
        deliver: false,
        channels: [],
      });
      await fetchTasks();
      showSuccess(`Task "${newTask.name}" updated successfully`);
    } catch (err) {
      showError('Failed to update task');
      console.error('Error updating task:', err);
    }
  };

  const handleCloseModal = () => {
    setShowAddModal(false);
    setEditingTask(null);
    setNewTask({
      name: '',
      scheduleKind: 'every',
      everyMs: 3600000,
      expr: '',
      message: '',
      deliver: false,
      channels: [],
    });
  };

  const getScheduleIcon = (kind: string) => {
    switch (kind) {
      case 'every':
        return (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        );
      case 'cron':
        return (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        );
      default:
        return (
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  const formatSchedule = (schedule: TaskSchedule) => {
    if (schedule.kind === 'every' && schedule.every_ms) {
      const seconds = Math.floor(schedule.every_ms / 1000);
      const minutes = Math.floor(seconds / 60);
      const hours = Math.floor(minutes / 60);
      const days = Math.floor(hours / 24);
      
      if (days > 0) return `Every ${days} days`;
      if (hours > 0) return `Every ${hours} hours`;
      if (minutes > 0) return `Every ${minutes} minutes`;
      return `Every ${seconds} seconds`;
    }
    if (schedule.kind === 'cron' && schedule.expr) {
      return `Cron: ${schedule.expr}`;
    }
    if (schedule.kind === 'at' && schedule.at_ms) {
      return formatAbsoluteTime(schedule.at_ms);
    }
    return 'Unknown schedule';
  };

  const filteredTasks = tasks.filter(task => {
    if (filter === 'enabled') return task.enabled;
    if (filter === 'disabled') return !task.enabled;
    return true;
  });

  const enabledCount = tasks.filter(t => t.enabled).length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex space-x-2">
          <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
          <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto bg-surface-50 min-h-full py-6 px-4 sm:px-6 lg:px-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-surface-900 flex items-center gap-3">
            Scheduled Tasks
            <Badge variant="default" size="sm">{tasks.length} tasks</Badge>
          </h2>
          <p className="text-sm text-surface-600 mt-1">
            {enabledCount} enabled · {tasks.length - enabledCount} disabled
          </p>
        </div>
        <Button onClick={() => setShowAddModal(true)} variant="primary">
          <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Add Task
        </Button>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setFilter('all')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
            filter === 'all' 
              ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50' 
              : 'bg-surface-100 text-surface-600 hover:text-surface-900 hover:bg-surface-200'
          }`}
        >
          All
        </button>
        <button
          onClick={() => setFilter('enabled')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
            filter === 'enabled' 
              ? 'bg-semantic-success/20 text-semantic-success border border-semantic-success/50' 
              : 'bg-surface-100 text-surface-600 hover:text-surface-900 hover:bg-surface-200'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-semantic-success"></span>
          Enabled
        </button>
        <button
          onClick={() => setFilter('disabled')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
            filter === 'disabled' 
              ? 'bg-surface-200 text-surface-700 border-surface-300' 
              : 'bg-surface-100 text-surface-600 hover:text-surface-900 hover:bg-surface-200'
          }`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-surface-500"></span>
          Disabled
        </button>
      </div>

      {error && (
        <div className="bg-semantic-error/20 border border-semantic-error/50 text-semantic-error p-3 rounded-lg flex items-center gap-2">
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
        </div>
      )}
      
      {filteredTasks.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center h-64">
            <svg className="w-12 h-12 mb-3 text-surface-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-surface-600 mb-2">No scheduled tasks yet</p>
            <button
              onClick={() => setShowAddModal(true)}
              className="text-primary-400 hover:text-primary-300 transition-colors text-sm"
            >
              Create your first task →
            </button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {filteredTasks.map((task) => {
            const nextRunText = task.state.next_run_at_ms ? formatRelativeTime(task.state.next_run_at_ms) : 'Not scheduled';
            
            return (
              <Card 
                key={task.id} 
                className={`group relative overflow-hidden transition-all duration-300 ${!task.enabled ? 'opacity-60 hover:opacity-80' : 'hover:shadow-lg hover:shadow-primary-500/10'}`}
              >
                <div className={`absolute inset-0 bg-gradient-to-r ${
                  task.enabled 
                    ? 'from-primary-500/5 via-transparent to-accent-emerald/5' 
                    : 'from-surface-200/30 via-transparent to-surface-200/30'
                } opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                <CardContent className="p-3.5 relative z-10">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${task.enabled ? 'bg-semantic-success shadow-sm shadow-semantic-success/50' : 'bg-surface-500'}`} />
                    
                    <div className={`flex items-center gap-1.5 flex-shrink-0 text-xs ${
                      task.enabled ? 'text-primary-400' : 'text-surface-500'
                    }`}>
                      {getScheduleIcon(task.schedule.kind)}
                      <span className="hidden sm:inline">{formatSchedule(task.schedule)}</span>
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-surface-900 truncate">{task.name}</h3>
                        {!task.enabled && (
                          <Badge variant="default" size="sm">Disabled</Badge>
                        )}
                      </div>
                      <p className="text-xs text-surface-600 truncate">{task.payload.message}</p>
                      {task.payload.deliver && (task.payload.channels?.length || (task.payload.channel && task.payload.to)) && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(task.payload.channels || [{ channel: task.payload.channel!, to: task.payload.to! }]).map((ch, idx) => (
                            <Badge key={idx} variant="info" size="sm">
                              {ch.channel}: {ch.to.length > 15 ? ch.to.substring(0, 15) + '...' : ch.to}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                    
                    <div className="text-right flex-shrink-0 min-w-[80px]">
                      <p className="font-medium text-sm text-surface-700">{nextRunText}</p>
                      <p className="text-xs text-surface-600">{task.state.next_run_at_ms ? formatAbsoluteTime(task.state.next_run_at_ms) : '-'}</p>
                    </div>
                    
                    <div className="flex items-center gap-1 opacity-80 hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleEditTask(task)}
                        className="p-1.5 text-surface-600 hover:bg-surface-200 rounded transition-all"
                        title="Edit"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      
                      <button
                        onClick={() => handleToggleTask(task.id, task.enabled, task.name)}
                        className={`p-1.5 rounded transition-all ${
                          task.enabled 
                            ? 'text-semantic-warning hover:bg-semantic-warning/20' 
                            : 'text-semantic-success hover:bg-semantic-success/20'
                        }`}
                        title={task.enabled ? 'Disable' : 'Enable'}
                      >
                        {task.enabled ? (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        )}
                      </button>
                      
                      <button
                        onClick={() => handleRunTask(task.id, task.name)}
                        className={`p-1.5 rounded transition-all ${
                          runningTasks.has(task.id)
                            ? 'text-semantic-warning bg-semantic-warning/20 animate-pulse'
                            : 'text-primary-400 hover:bg-primary-500/20'
                        }`}
                        title={runningTasks.has(task.id) ? 'Running...' : 'Run Now'}
                        disabled={runningTasks.has(task.id)}
                      >
                        {runningTasks.has(task.id) ? (
                          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        )}
                      </button>
                      
                      <button
                        onClick={() => handleDeleteTask(task.id, task.name)}
                        className="p-1.5 text-semantic-error hover:bg-semantic-error/20 rounded transition-all"
                        title="Delete"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  {task.state.last_run_at_ms && (
                    <div className="mt-2 pt-2 border-t border-surface-200">
                      <div className="flex items-center gap-3 text-xs text-surface-600">
                        <span>Last run: {formatRelativeTime(task.state.last_run_at_ms)}</span>
                        {task.state.last_status && (
                          <span className={task.state.last_status === 'ok' ? 'text-semantic-success' : 'text-semantic-error'}>
                            {task.state.last_status === 'ok' ? '✓ Success' : '✗ Failed'}
                          </span>
                        )}
                        {task.state.last_error && (
                          <span className="text-semantic-error truncate max-w-[200px]">
                            {task.state.last_error}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Modal isOpen={showAddModal} onClose={handleCloseModal} title={editingTask ? 'Edit Task' : 'Add Scheduled Task'}>
        <div className="space-y-4">
          <Input
            label="Task Name *"
            value={newTask.name}
            onChange={(e) => setNewTask({ ...newTask, name: e.target.value })}
            placeholder="e.g., Water reminder"
          />

          <div>
            <label className="block text-sm font-medium text-surface-700 mb-2">Schedule Type</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setNewTask({ ...newTask, scheduleKind: 'every' })}
                className={`p-2.5 rounded-lg border transition-all text-sm ${
                  newTask.scheduleKind === 'every'
                    ? 'bg-primary-500/20 border-primary-500/50 text-primary-400'
                    : 'bg-surface-50 border-surface-200 text-surface-700 hover:border-surface-300'
                }`}
              >
                <div className="flex items-center justify-center gap-1.5">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Interval Repeat
                </div>
              </button>
              <button
                type="button"
                onClick={() => setNewTask({ ...newTask, scheduleKind: 'cron' })}
                className={`p-2.5 rounded-lg border transition-all text-sm ${
                  newTask.scheduleKind === 'cron'
                    ? 'bg-primary-500/20 border-primary-500/50 text-primary-400'
                    : 'bg-surface-50 border-surface-200 text-surface-700 hover:border-surface-300'
                }`}
              >
                <div className="flex items-center justify-center gap-1.5">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Cron Expression
                </div>
              </button>
            </div>
          </div>

          {newTask.scheduleKind === 'every' && (
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  label="Repeat Interval"
                  type="number"
                  value={String(newTask.everyMs / 3600000)}
                  onChange={(v) => setNewTask({ ...newTask, everyMs: Number(v) * 3600000 })}
                  placeholder="1"
                />
              </div>
              <div className="flex items-end">
                <span className="px-3 py-2.5 bg-surface-100 border border-surface-200 rounded-lg text-surface-700 text-sm">
                  Hours
                </span>
              </div>
            </div>
          )}

          {newTask.scheduleKind === 'cron' && (
            <div>
              <Input
                label="Cron Expression"
                value={newTask.expr}
                onChange={(e) => setNewTask({ ...newTask, expr: e.target.value })}
                placeholder="0 9 * * * (daily at 9 AM)"
                className="font-mono"
              />
              <p className="text-xs text-surface-600 mt-1">Format: minute hour day month weekday</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-surface-700 mb-2">Message Content *</label>
            <textarea
              value={newTask.message}
              onChange={(e) => setNewTask({ ...newTask, message: e.target.value })}
              className="w-full bg-surface-50 border border-surface-200 rounded-lg px-3 py-2 text-surface-900 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
              rows={2}
              placeholder="e.g., Time to drink water! 💧"
            />
          </div>

          <div className="flex items-center gap-2 p-3 bg-surface-100 rounded-lg">
            <input
              type="checkbox"
              id="deliver"
              checked={newTask.deliver}
              onChange={(e) => setNewTask({ ...newTask, deliver: e.target.checked })}
              className="w-4 h-4 rounded border-surface-600 text-primary-500 focus:ring-primary-500"
            />
            <label htmlFor="deliver" className="text-sm text-surface-700">
              Push to Channels
            </label>
          </div>

          {newTask.deliver && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-surface-700">Delivery Channels</label>
                <button
                  type="button"
                  onClick={handleAddChannel}
                  className="text-sm text-primary-400 hover:text-primary-300 flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  Add Channel
                </button>
              </div>
              
              {newTask.channels.length === 0 && (
                <p className="text-xs text-surface-500 italic">Click "Add Channel" to add delivery targets</p>
              )}
              
              {newTask.channels.map((ch, index) => (
                <div key={index} className="flex gap-2 items-start p-2 bg-surface-50 rounded-lg border border-surface-200">
                  <div className="flex-1 grid grid-cols-2 gap-2">
                    <Input
                      label="Channel"
                      value={ch.channel}
                      onChange={(e) => handleUpdateChannel(index, 'channel', e.target.value)}
                      placeholder="web, sharecrm, telegram..."
                    />
                    <Input
                      label="Recipient"
                      value={ch.to}
                      onChange={(e) => handleUpdateChannel(index, 'to', e.target.value)}
                      placeholder="session_key, chat_id..."
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveChannel(index)}
                    className="mt-6 p-1.5 text-semantic-error hover:bg-semantic-error/20 rounded transition-all"
                    title="Remove"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <Button variant="secondary" onClick={handleCloseModal}>
            Cancel
          </Button>
          <Button variant="primary" onClick={editingTask ? handleUpdateTask : handleAddTask}>
            {editingTask ? 'Update' : 'Add'}
          </Button>
        </div>
      </Modal>
    </div>
  );
};

export default TasksPage;
