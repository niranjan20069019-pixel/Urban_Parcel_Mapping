import { useState, useEffect, useCallback, useRef } from 'react';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useApi<T>(
  fetcher: (signal?: AbortSignal) => Promise<T>,
  deps: any[] = []
): UseApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const mounted = useRef(true);

  const run = useCallback(() => {
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    fetcher(controller.signal)
      .then((data) => mounted.current && setState({ data, loading: false, error: null }))
      .catch((err) => {
        if (err.name !== 'CanceledError' && mounted.current) {
          setState({ data: null, loading: false, error: err.message ?? String(err) });
        }
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mounted.current = true;
    const cleanup = run();
    return () => { mounted.current = false; cleanup(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

  return { ...state, refetch: run };
}

export function useMutation<TArgs, TResult>(
  mutator: (args: TArgs) => Promise<TResult>
) {
  const [state, setState] = useState<UseApiState<TResult>>({
    data: null,
    loading: false,
    error: null,
  });

  const mutate = useCallback(
    async (args: TArgs): Promise<TResult> => {
      setState({ data: null, loading: true, error: null });
      try {
        const result = await mutator(args);
        setState({ data: result, loading: false, error: null });
        return result;
      } catch (err: any) {
        const msg = err.message ?? String(err);
        setState({ data: null, loading: false, error: msg });
        throw err;
      }
    },
    [mutator]
  );

  return { ...state, mutate };
}
