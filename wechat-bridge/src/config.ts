/**
 * Token persistence and configuration for wechat-bridge.
 * Stores/loads WeChat session credentials to ~/.adam/wechat/.
 */
import fs from "node:fs";
import path from "node:path";
import { homedir } from "node:os";

export const DEFAULT_API_BASE_URL = "https://ilinkai.weixin.qq.com";
export const DEFAULT_CHANNEL_ID = "default";
export const DEFAULT_PERMISSION_TIMEOUT_MS = 120_000;

const WECHAT_CONFIG_DIR = path.join(homedir(), ".adam", "wechat");

export interface WeChatBridgeConfig {
  botToken: string;
  accountId: string;
  baseUrl: string;
  userId: string;
  routeTag?: string;
  createdAt: number;
}

function configPath(channelId: string): string {
  return path.join(WECHAT_CONFIG_DIR, `${channelId}.json`);
}

export function loadConfig(channelId: string): WeChatBridgeConfig | null {
  try {
    const raw = fs.readFileSync(configPath(channelId), "utf-8");
    const parsed = JSON.parse(raw) as WeChatBridgeConfig;
    if (!parsed.botToken || !parsed.baseUrl) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveConfig(channelId: string, config: WeChatBridgeConfig): void {
  fs.mkdirSync(WECHAT_CONFIG_DIR, { recursive: true });
  fs.writeFileSync(configPath(channelId), JSON.stringify(config, null, 2), "utf-8");
}

/** Load sync buf for getUpdates long-poll state persistence. */
export function loadSyncBuf(channelId: string): string {
  try {
    return fs.readFileSync(path.join(WECHAT_CONFIG_DIR, `${channelId}.sync`), "utf-8");
  } catch {
    return "";
  }
}

/** Save sync buf after each successful getUpdates poll. */
export function saveSyncBuf(channelId: string, buf: string): void {
  fs.mkdirSync(WECHAT_CONFIG_DIR, { recursive: true });
  fs.writeFileSync(path.join(WECHAT_CONFIG_DIR, `${channelId}.sync`), buf, "utf-8");
}
