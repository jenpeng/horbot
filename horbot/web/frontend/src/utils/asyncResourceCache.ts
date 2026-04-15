type CacheKeyFn<TArgs extends unknown[]> = (...args: TArgs) => string;

interface CacheEntry<TResult> {
  value: TResult;
  expiresAt: number;
}

interface AsyncResourceCacheOptions<TArgs extends unknown[]> {
  ttlMs: number;
  keyFn?: CacheKeyFn<TArgs>;
}

export interface AsyncResourceCache<TArgs extends unknown[], TResult> {
  get: (...args: TArgs) => Promise<TResult>;
  refresh: (...args: TArgs) => Promise<TResult>;
  peek: (...args: TArgs) => TResult | undefined;
  invalidate: (...args: TArgs) => void;
  clear: () => void;
}

const defaultKeyFn = <TArgs extends unknown[]>(...args: TArgs): string => JSON.stringify(args);

export const createAsyncResourceCache = <TArgs extends unknown[], TResult>(
  loader: (...args: TArgs) => Promise<TResult>,
  options: AsyncResourceCacheOptions<TArgs>,
): AsyncResourceCache<TArgs, TResult> => {
  const entries = new Map<string, CacheEntry<TResult>>();
  const inflight = new Map<string, Promise<TResult>>();
  const keyFn = options.keyFn || defaultKeyFn<TArgs>;

  const peek = (...args: TArgs): TResult | undefined => {
    const key = keyFn(...args);
    const entry = entries.get(key);
    if (!entry) {
      return undefined;
    }
    if (entry.expiresAt <= Date.now()) {
      entries.delete(key);
      return undefined;
    }
    return entry.value;
  };

  const run = async (force: boolean, ...args: TArgs): Promise<TResult> => {
    const key = keyFn(...args);

    if (!force) {
      const cached = peek(...args);
      if (cached !== undefined) {
        return cached;
      }
    }

    const existingPromise = inflight.get(key);
    if (existingPromise) {
      return existingPromise;
    }

    const promise = loader(...args)
      .then((value) => {
        entries.set(key, {
          value,
          expiresAt: Date.now() + options.ttlMs,
        });
        inflight.delete(key);
        return value;
      })
      .catch((error) => {
        inflight.delete(key);
        throw error;
      });

    inflight.set(key, promise);
    return promise;
  };

  return {
    get: (...args: TArgs) => run(false, ...args),
    refresh: (...args: TArgs) => run(true, ...args),
    peek,
    invalidate: (...args: TArgs) => {
      entries.delete(keyFn(...args));
      inflight.delete(keyFn(...args));
    },
    clear: () => {
      entries.clear();
      inflight.clear();
    },
  };
};
