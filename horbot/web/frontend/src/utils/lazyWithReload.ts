import { lazy } from 'react';

const CHUNK_ERROR_PATTERNS = [
  /ChunkLoadError/i,
  /Failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /Importing a module script failed/i,
];

const RETRY_PREFIX = 'horbot:lazy-retry:';

const isRecoverableChunkError = (error: unknown): boolean => {
  const message = error instanceof Error ? error.message : String(error ?? '');
  return CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
};

const getRetryKey = (key: string): string => `${RETRY_PREFIX}${key}`;

export const lazyWithReload = <T extends React.ComponentType<any>>(
  key: string,
  loader: () => Promise<{ default: T }>,
) =>
  lazy(async () => {
    try {
      const module = await loader();
      if (typeof window !== 'undefined') {
        window.sessionStorage.removeItem(getRetryKey(key));
      }
      return module;
    } catch (error) {
      if (typeof window !== 'undefined' && isRecoverableChunkError(error)) {
        const retryKey = getRetryKey(key);
        const alreadyRetried = window.sessionStorage.getItem(retryKey) === '1';

        if (!alreadyRetried) {
          window.sessionStorage.setItem(retryKey, '1');
          window.location.reload();
          return new Promise<never>(() => {});
        }

        window.sessionStorage.removeItem(retryKey);
        throw new Error('前端资源已更新但当前标签页仍引用旧文件。请刷新页面后重试。');
      }

      throw error;
    }
  });

export const installVitePreloadReload = (): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.addEventListener('vite:preloadError', (event) => {
    const preloadEvent = event as Event & { payload?: unknown };
    const error = preloadEvent.payload ?? event;

    if (!isRecoverableChunkError(error)) {
      return;
    }

    const retryKey = getRetryKey('vite-preload');
    const alreadyRetried = window.sessionStorage.getItem(retryKey) === '1';

    if (alreadyRetried) {
      window.sessionStorage.removeItem(retryKey);
      return;
    }

    event.preventDefault();
    window.sessionStorage.setItem(retryKey, '1');
    window.location.reload();
  });
};
