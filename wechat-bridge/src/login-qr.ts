/**
 * WeChat QR scan authentication for wechat-bridge plugin.
 * Origin: Adam WeChat adapter → QR login flow.
 */
import { randomUUID } from "node:crypto";

type ActiveLogin = {
  sessionKey: string;
  id: string;
  qrcode: string;
  qrcodeUrl: string;
  startedAt: number;
  botToken?: string;
  status?: "wait" | "scaned" | "confirmed" | "expired";
};

const ACTIVE_LOGIN_TTL_MS = 5 * 60_000;
const QR_LONG_POLL_TIMEOUT_MS = 35_000;

export const DEFAULT_ILINK_BOT_TYPE = "3";

const activeLogins = new Map<string, ActiveLogin>();

interface QRCodeResponse {
  qrcode: string;
  qrcode_img_content: string;
}

interface StatusResponse {
  status: "wait" | "scaned" | "confirmed" | "expired";
  bot_token?: string;
  ilink_bot_id?: string;
  baseurl?: string;
  ilink_user_id?: string;
}

function isLoginFresh(login: ActiveLogin): boolean {
  return Date.now() - login.startedAt < ACTIVE_LOGIN_TTL_MS;
}

function purgeExpiredLogins(): void {
  for (const [id, login] of activeLogins) {
    if (!isLoginFresh(login)) {
      activeLogins.delete(id);
    }
  }
}

async function fetchQRCode(apiBaseUrl: string, botType: string, routeTag?: string): Promise<QRCodeResponse> {
  const base = apiBaseUrl.endsWith("/") ? apiBaseUrl : `${apiBaseUrl}/`;
  const url = new URL(`ilink/bot/get_bot_qrcode?bot_type=${encodeURIComponent(botType)}`, base);

  const headers: Record<string, string> = {};
  if (routeTag) {
    headers.SKRouteTag = routeTag;
  }

  const response = await fetch(url.toString(), { headers });
  if (!response.ok) {
    const body = await response.text().catch(() => "(unreadable)");
    throw new Error(`Failed to fetch QR code: ${response.status} ${response.statusText} body=${body}`);
  }
  return await response.json() as QRCodeResponse;
}

async function pollQRStatus(apiBaseUrl: string, qrcode: string, routeTag?: string): Promise<StatusResponse> {
  const base = apiBaseUrl.endsWith("/") ? apiBaseUrl : `${apiBaseUrl}/`;
  const url = new URL(`ilink/bot/get_qrcode_status?qrcode=${encodeURIComponent(qrcode)}`, base);

  const headers: Record<string, string> = {
    "iLink-App-ClientVersion": "1",
  };
  if (routeTag) {
    headers.SKRouteTag = routeTag;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), QR_LONG_POLL_TIMEOUT_MS);
  try {
    const response = await fetch(url.toString(), { headers, signal: controller.signal });
    clearTimeout(timer);
    const rawText = await response.text();
    if (!response.ok) {
      throw new Error(`Failed to poll QR status: ${response.status} ${response.statusText}`);
    }
    return JSON.parse(rawText) as StatusResponse;
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof Error && err.name === "AbortError") {
      return { status: "wait" };
    }
    throw err;
  }
}

export type WeixinQrStartResult = {
  qrcodeUrl?: string;
  message: string;
  sessionKey: string;
};

export type WeixinQrWaitResult = {
  connected: boolean;
  botToken?: string;
  accountId?: string;
  baseUrl?: string;
  userId?: string;
  message: string;
};

export async function startWeixinLoginWithQr(opts: {
  force?: boolean;
  accountId?: string;
  apiBaseUrl: string;
  botType?: string;
  routeTag?: string;
}): Promise<WeixinQrStartResult> {
  const sessionKey = opts.accountId || randomUUID();

  purgeExpiredLogins();

  const existing = activeLogins.get(sessionKey);
  if (!opts.force && existing && isLoginFresh(existing) && existing.qrcodeUrl) {
    return {
      qrcodeUrl: existing.qrcodeUrl,
      message: "QR code ready. Scan with WeChat.",
      sessionKey,
    };
  }

  if (!opts.apiBaseUrl) {
    return {
      message: "No baseUrl configured for this WeChat channel.",
      sessionKey,
    };
  }

  try {
    const botType = opts.botType || DEFAULT_ILINK_BOT_TYPE;
    const qrResponse = await fetchQRCode(opts.apiBaseUrl, botType, opts.routeTag);

    const login: ActiveLogin = {
      sessionKey,
      id: randomUUID(),
      qrcode: qrResponse.qrcode,
      qrcodeUrl: qrResponse.qrcode_img_content,
      startedAt: Date.now(),
    };

    activeLogins.set(sessionKey, login);

    return {
      qrcodeUrl: qrResponse.qrcode_img_content,
      message: "Scan the QR code with WeChat to connect.",
      sessionKey,
    };
  } catch (err) {
    return {
      message: `Failed to start login: ${String(err)}`,
      sessionKey,
    };
  }
}

const MAX_QR_REFRESH_COUNT = 3;

export async function waitForWeixinLogin(opts: {
  timeoutMs?: number;
  sessionKey: string;
  apiBaseUrl: string;
  botType?: string;
  routeTag?: string;
}): Promise<WeixinQrWaitResult> {
  const activeLogin = activeLogins.get(opts.sessionKey);

  if (!activeLogin) {
    return { connected: false, message: "No active login session. Start QR login first." };
  }

  if (!isLoginFresh(activeLogin)) {
    activeLogins.delete(opts.sessionKey);
    return { connected: false, message: "QR code expired. Please start again." };
  }

  const timeoutMs = Math.max(opts.timeoutMs ?? 480_000, 1000);
  const deadline = Date.now() + timeoutMs;
  let qrRefreshCount = 1;

  while (Date.now() < deadline) {
    try {
      const statusResponse = await pollQRStatus(opts.apiBaseUrl, activeLogin.qrcode, opts.routeTag);
      activeLogin.status = statusResponse.status;

      switch (statusResponse.status) {
        case "wait":
          break;
        case "scaned":
          break;
        case "expired": {
          qrRefreshCount++;
          if (qrRefreshCount > MAX_QR_REFRESH_COUNT) {
            activeLogins.delete(opts.sessionKey);
            return { connected: false, message: "Login timeout: QR expired multiple times." };
          }
          try {
            const botType = opts.botType || DEFAULT_ILINK_BOT_TYPE;
            const qrResponse = await fetchQRCode(opts.apiBaseUrl, botType, opts.routeTag);
            activeLogin.qrcode = qrResponse.qrcode;
            activeLogin.qrcodeUrl = qrResponse.qrcode_img_content;
            activeLogin.startedAt = Date.now();
          } catch (refreshErr) {
            activeLogins.delete(opts.sessionKey);
            return { connected: false, message: `QR refresh failed: ${String(refreshErr)}` };
          }
          break;
        }
        case "confirmed": {
          if (!statusResponse.ilink_bot_id) {
            activeLogins.delete(opts.sessionKey);
            return { connected: false, message: "Login failed: server did not return bot ID." };
          }

          activeLogins.delete(opts.sessionKey);

          return {
            connected: true,
            botToken: statusResponse.bot_token,
            accountId: statusResponse.ilink_bot_id,
            baseUrl: statusResponse.baseurl,
            userId: statusResponse.ilink_user_id,
            message: "Connected to WeChat successfully!",
          };
        }
      }
    } catch (err) {
      activeLogins.delete(opts.sessionKey);
      return { connected: false, message: `Login failed: ${String(err)}` };
    }

    await new Promise((r) => setTimeout(r, 1000));
  }

  activeLogins.delete(opts.sessionKey);
  return { connected: false, message: "Login timeout. Please try again." };
}
