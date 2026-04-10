import type { TeamsPageSelection } from './types';

export const readSelectionFromUrl = (): TeamsPageSelection | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const params = new URLSearchParams(window.location.search);
  const agentId = params.get('agent')?.trim();
  if (agentId) {
    return { kind: 'agent', id: agentId };
  }

  const teamId = params.get('team')?.trim();
  if (teamId) {
    return { kind: 'team', id: teamId };
  }

  return null;
};

export const writeSelectionToUrl = (selection: TeamsPageSelection | null): void => {
  if (typeof window === 'undefined') {
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.delete('agent');
  url.searchParams.delete('team');
  url.searchParams.delete('focus');

  if (selection?.kind === 'agent' && selection.id) {
    url.searchParams.set('agent', selection.id);
  } else if (selection?.kind === 'team' && selection.id) {
    url.searchParams.set('team', selection.id);
  }

  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(null, '', nextUrl);
};
