import { useEffect, useState } from "react";

/**
 * The value once it has stopped changing for `delay` ms. Filters use it so that arrowing
 * through a closed select (which fires a change for every option in Chrome on Windows)
 * loads and announces only the option the user stops on.
 */
export function useDebounced<T>(value: T, delay = 500): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}
