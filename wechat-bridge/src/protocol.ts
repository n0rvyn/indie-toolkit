/**
 * Channel protocol adapter layer (DP-001 Option B).
 * Wraps MCP experimental notification names behind an interface so future
 * API changes only require adding a new protocol version class.
 */
import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { z } from "zod";

// --- Interface ---

export interface ChannelProtocol {
  /** Push a message from WeChat into the Claude Code session. */
  sendChannelMessage(content: string, meta?: Record<string, string>): Promise<void>;
  /** Return a permission verdict (allow/deny) to Claude Code. */
  sendPermissionVerdict(requestId: string, behavior: "allow" | "deny"): Promise<void>;
  /** Register a handler for incoming permission requests from Claude Code. */
  onPermissionRequest(handler: PermissionRequestHandler): void;
}

export interface PermissionRequestParams {
  request_id: string;
  tool_name: string;
  description: string;
  input_preview: string;
}

export type PermissionRequestHandler = (params: PermissionRequestParams) => void | Promise<void>;

// --- V1: Current experimental protocol ---

const CHANNEL_NOTIFICATION = "notifications/claude/channel";
const PERMISSION_REQUEST_NOTIFICATION = "notifications/claude/channel/permission_request";
const PERMISSION_VERDICT_NOTIFICATION = "notifications/claude/channel/permission";

const PermissionRequestSchema = z.object({
  method: z.literal(PERMISSION_REQUEST_NOTIFICATION),
  params: z.object({
    request_id: z.string(),
    tool_name: z.string(),
    description: z.string(),
    input_preview: z.string(),
  }),
});

export class McpChannelProtocolV1 implements ChannelProtocol {
  constructor(private server: Server) {}

  async sendChannelMessage(content: string, meta?: Record<string, string>): Promise<void> {
    await this.server.notification({
      method: CHANNEL_NOTIFICATION,
      params: { content, meta },
    });
  }

  async sendPermissionVerdict(requestId: string, behavior: "allow" | "deny"): Promise<void> {
    await this.server.notification({
      method: PERMISSION_VERDICT_NOTIFICATION,
      params: { request_id: requestId, behavior },
    });
  }

  onPermissionRequest(handler: PermissionRequestHandler): void {
    this.server.setNotificationHandler(PermissionRequestSchema, async ({ params }) => {
      await handler(params);
    });
  }
}

// --- Factory ---

/**
 * Create the appropriate protocol adapter for the given MCP server.
 * Currently only V1 (experimental) exists; future versions can be added here.
 */
export function createProtocol(server: Server): ChannelProtocol {
  return new McpChannelProtocolV1(server);
}
