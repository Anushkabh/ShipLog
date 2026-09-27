"use client";

import * as React from "react";

/**
 * window.location.origin, but "" during server render and the first client
 * render — so SSR and hydration produce identical markup (reading `window`
 * inline causes a hydration mismatch).
 */
export function useOrigin(): string {
  const [origin, setOrigin] = React.useState("");
  React.useEffect(() => setOrigin(window.location.origin), []);
  return origin;
}
