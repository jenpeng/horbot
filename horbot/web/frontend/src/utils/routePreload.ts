const routePreloaders = new Map<string, () => Promise<unknown>>();
const routeInflight = new Map<string, Promise<unknown>>();

export const registerRoutePreload = (
  path: string,
  loader: () => Promise<unknown>,
): void => {
  routePreloaders.set(path, loader);
};

export const preloadRoute = async (path: string): Promise<void> => {
  const loader = routePreloaders.get(path);
  if (!loader) {
    return;
  }

  const existing = routeInflight.get(path);
  if (existing) {
    await existing;
    return;
  }

  const promise = loader()
    .catch((error) => {
      console.warn(`Failed to preload route "${path}"`, error);
    })
    .finally(() => {
      routeInflight.delete(path);
    });

  routeInflight.set(path, promise);
  await promise;
};

export const preloadRoutesSequentially = async (paths: string[]): Promise<void> => {
  for (const path of paths) {
    await preloadRoute(path);
  }
};
