import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import TaskWorkbenchPopover from './TaskWorkbenchPopover';

const t = (key: string, values?: Record<string, string | number>) => {
  if (key === 'chat.workbenchTitle') return 'Task Workbench';
  if (key === 'chat.workbenchTurns') return `${values?.count} turns`;
  if (key === 'chat.workbenchFiles') return `${values?.count} files`;
  if (key === 'chat.workbenchSteps') return `${values?.count} steps`;
  if (key === 'chat.workbenchLatestRequest') return `Latest request: ${values?.preview}`;
  if (key === 'chat.workbenchCollapse') return 'Close workbench';
  if (key === 'chat.workbenchUseSummary') return 'Use summary';
  if (key === 'chat.workbenchSearchRequest') return 'Search request';
  if (key === 'chat.workbenchCopySummary') return 'Copy summary';
  return key;
};

const baseProps = {
  t,
  isOpen: true,
  isLoading: false,
  turnCount: 2,
  workbench: {
    latestRequest: 'Create a clean PPT summary',
    stage: 'Done',
    activeAgents: ['Agent A'],
    fileCount: 1,
    executionSteps: 1,
    runningSteps: 0,
    failedSteps: 0,
    toolNames: ['officecli'],
  },
  quickActions: [{ id: 'review-files', label: 'Review files', prompt: 'Review attached files' }],
  onToggle: vi.fn(),
  onClose: vi.fn(),
  onUseSummary: vi.fn(),
  onSearchRequest: vi.fn(),
  onCopySummary: vi.fn(),
  onApplyQuickAction: vi.fn(),
};

describe('TaskWorkbenchPopover', () => {
  it('closes when clicking outside the popover', () => {
    const onClose = vi.fn();
    render(
      <>
        <button type="button">Outside</button>
        <TaskWorkbenchPopover {...baseProps} onClose={onClose} />
      </>,
    );

    expect(screen.getByTestId('chat-workbench-panel')).toBeInTheDocument();
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Outside' }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when pressing Escape', () => {
    const onClose = vi.fn();
    render(<TaskWorkbenchPopover {...baseProps} onClose={onClose} />);

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
