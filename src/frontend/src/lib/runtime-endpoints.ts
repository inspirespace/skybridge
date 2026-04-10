const AUTH_LOCAL_FALLBACK_URL = "http://localhost:9099";
const FIRESTORE_LOCAL_FALLBACK_URL = "http://localhost:8080";

export type RuntimeLocationLike = {
  origin: string;
  protocol: string;
  hostname: string;
};

const trimTrailingSlashes = (value: string) => value.replace(/\/+$/, "");

const withHttpScheme = (value: string) => {
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return value;
  }
  return `http://${value}`;
};

const getRuntimeLocation = (runtimeLocation?: RuntimeLocationLike): RuntimeLocationLike | null => {
  if (runtimeLocation) return runtimeLocation;
  if (typeof window === "undefined") return null;
  return {
    origin: window.location.origin,
    protocol: window.location.protocol,
    hostname: window.location.hostname,
  };
};

const normalizeBaseUrl = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const withScheme = withHttpScheme(trimmed);
  try {
    return trimTrailingSlashes(new URL(withScheme).toString());
  } catch {
    return trimTrailingSlashes(withScheme);
  }
};

const normalizeHost = (host: string) => host.trim().toLowerCase().replace(/\.$/, "");

const isSameHostOrSubdomain = (host: string, runtimeHost: string) => {
  const nextHost = normalizeHost(host);
  const baseHost = normalizeHost(runtimeHost);
  if (!nextHost || !baseHost) return false;
  return nextHost === baseHost || nextHost.endsWith(`.${baseHost}`);
};

const isLoopbackHost = (host: string) => {
  const normalized = normalizeHost(host);
  return normalized === "localhost" || normalized === "127.0.0.1" || normalized === "::1";
};

const parseOriginHostPort = (baseUrl: string) => {
  const parsed = new URL(baseUrl);
  const isHttps = parsed.protocol === "https:";
  const defaultPort = isHttps ? 443 : 80;
  const port = parsed.port ? Number.parseInt(parsed.port, 10) : defaultPort;
  return {
    host: parsed.hostname,
    port: Number.isFinite(port) ? port : defaultPort,
    isHttps,
  };
};

export const resolveApiBaseUrl = (configuredApiBaseUrl: string) => {
  const configured = configuredApiBaseUrl.trim();
  const base = configured || "/api";
  return trimTrailingSlashes(base);
};

export const resolveAuthEmulatorBaseUrl = ({
  useEmulator,
  explicitHost,
  runtimeLocation,
}: {
  useEmulator?: boolean;
  explicitHost?: string;
  runtimeLocation?: RuntimeLocationLike;
}) => {
  if (!useEmulator) return undefined;
  const runtime = getRuntimeLocation(runtimeLocation);
  const explicit = explicitHost?.trim() ?? "";
  if (explicit) {
    const normalized = normalizeBaseUrl(explicit);
    if (runtime?.protocol === "http:" && normalized.startsWith("https://")) {
      return AUTH_LOCAL_FALLBACK_URL;
    }
    return normalized;
  }
  if (runtime?.protocol === "https:") {
    return trimTrailingSlashes(runtime.origin);
  }
  return AUTH_LOCAL_FALLBACK_URL;
};

export const resolveFirestoreEmulatorHostPort = ({
  useEmulator,
  explicitHost,
  runtimeLocation,
}: {
  useEmulator?: boolean;
  explicitHost?: string;
  runtimeLocation?: RuntimeLocationLike;
}) => {
  if (!useEmulator) {
    return null;
  }
  const authBase = resolveAuthEmulatorBaseUrl({
    useEmulator,
    explicitHost,
    runtimeLocation,
  });
  const runtime = getRuntimeLocation(runtimeLocation);
  const fallback = runtime?.protocol === "https:"
    ? trimTrailingSlashes(runtime.origin)
    : FIRESTORE_LOCAL_FALLBACK_URL;
  const baseUrl = authBase || fallback;
  try {
    const parsed = parseOriginHostPort(baseUrl);
    if (explicitHost?.trim()) {
      if (isLoopbackHost(parsed.host) && parsed.port === 9099) {
        return { host: parsed.host, port: 8080 };
      }
      return { host: parsed.host, port: parsed.port };
    }
    if (runtime?.protocol === "https:") {
      return { host: parsed.host, port: parsed.port };
    }
    const fallbackParsed = parseOriginHostPort(FIRESTORE_LOCAL_FALLBACK_URL);
    return { host: fallbackParsed.host, port: fallbackParsed.port };
  } catch {
    const fallbackParsed = parseOriginHostPort(FIRESTORE_LOCAL_FALLBACK_URL);
    return { host: fallbackParsed.host, port: fallbackParsed.port };
  }
};

export const rewriteHttpToHttpsForRuntimeHost = ({
  url,
  runtimeLocation,
}: {
  url: string;
  runtimeLocation?: RuntimeLocationLike;
}) => {
  const runtime = getRuntimeLocation(runtimeLocation);
  if (!runtime || runtime.protocol !== "https:") {
    return url;
  }
  let parsed: URL;
  try {
    parsed = new URL(url, runtime.origin);
  } catch {
    return url;
  }
  if (parsed.protocol !== "http:") {
    return url;
  }
  if (!isSameHostOrSubdomain(parsed.hostname, runtime.hostname)) {
    return url;
  }
  parsed.protocol = "https:";
  return parsed.toString();
};
