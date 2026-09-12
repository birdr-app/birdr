import { clientInfoHeaders } from './clientInfo';

let installed = false;
const originalFetch = globalThis.fetch.bind(globalThis);

/** Attach app identity headers to every fetch without failing if they are already set. */
export function installAppIdentityFetch(): void {
  if (installed) return;
  installed = true;
  globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const headers = new Headers(init?.headers);
    for (const [key, value] of Object.entries(clientInfoHeaders())) {
      if (value && !headers.has(key)) {
        headers.set(key, value);
      }
    }
    return originalFetch(input, { ...init, headers });
  };
}
