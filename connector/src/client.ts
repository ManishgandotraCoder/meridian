export interface CapabilityRow {
  group: string;
  capability: string;
  enabled: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

export interface UsageClient {
  usageSummary(group: string, period: string): Promise<unknown>;
  topUsers(group: string, period: string, limit: number): Promise<unknown>;
  capabilityStatus(group: string): Promise<CapabilityRow[]>;
  setCapability(group: string, capability: string, enabled: boolean): Promise<unknown>;
}

export class DeniedByApi extends Error {
  constructor(readonly denial: { error: "permission_denied"; reason: string; required_scope?: string }) {
    super(denial.reason);
  }
}

export class ServiceError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`usage service returned ${status}`);
  }
}

export class HttpUsageClient implements UsageClient {
  constructor(
    private readonly baseUrl: string,
    private readonly userId: string,
  ) {}

  usageSummary(group: string, period: string): Promise<unknown> {
    return this.request("GET", "/api/usage/summary", { group, period });
  }

  topUsers(group: string, period: string, limit: number): Promise<unknown> {
    return this.request("GET", "/api/usage/top-users", { group, period, limit: String(limit) });
  }

  async capabilityStatus(group: string): Promise<CapabilityRow[]> {
    const body = await this.request("GET", "/api/capabilities", { group });
    if (!Array.isArray(body)) throw new ServiceError(200, body);
    return body as CapabilityRow[];
  }

  setCapability(group: string, capability: string, enabled: boolean): Promise<unknown> {
    return this.request("PUT", "/api/capabilities", undefined, { group, capability, enabled });
  }

  private async request(
    method: "GET" | "PUT",
    pathname: string,
    query?: Record<string, string>,
    body?: unknown,
  ): Promise<unknown> {
    const url = new URL(pathname, this.baseUrl.endsWith("/") ? this.baseUrl : `${this.baseUrl}/`);
    if (query) {
      for (const [key, value] of Object.entries(query)) url.searchParams.set(key, value);
    }
    const response = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-User-Id": this.userId,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    const parsed = text ? JSON.parse(text) : null;
    if (response.status === 403 && parsed && parsed.error === "permission_denied") {
      throw new DeniedByApi(parsed);
    }
    if (!response.ok) throw new ServiceError(response.status, parsed);
    return parsed;
  }
}
