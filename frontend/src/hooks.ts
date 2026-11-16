import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

const KEYBOARD_SETTLE_MS = 1500;

/**
 * A filter control whose shown value changes at once but whose applied value (the one
 * that reloads data) waits for keyboard users. In Chrome on Windows, arrowing through a
 * closed select fires a change for every option, so applying each one reloaded the list
 * and announced every intermediate count. A pick with the mouse or from the open list
 * applies at once. A change made with keys applies on Enter, when focus leaves the
 * control, or after 1.5 seconds without another key.
 *
 * Spread `props` onto the select or input.
 */
export function useFilter<T extends string>(initial: T) {
  const [value, setValue] = useState<T>(initial);
  const [applied, setApplied] = useState<T>(initial);
  const fromKey = useRef(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function apply(next: T) {
    window.clearTimeout(timer.current);
    setApplied(next);
  }

  const props = {
    value,
    onKeyDown(event: KeyboardEvent<HTMLElement>) {
      if (event.key === "Enter") apply(value);
      else if (event.key !== "Tab") fromKey.current = true;
    },
    onChange(event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) {
      const next = event.target.value as T;
      setValue(next);
      if (fromKey.current) {
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => setApplied(next), KEYBOARD_SETTLE_MS);
      } else {
        apply(next);
      }
      fromKey.current = false;
    },
    onBlur() {
      fromKey.current = false;
      if (value !== applied) apply(value);
    },
  };

  return { value, applied, props };
}
