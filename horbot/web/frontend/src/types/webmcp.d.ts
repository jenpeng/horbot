interface MCPInputSchema {
  type: "object";
  properties: Record<string, {
    type: string;
    description: string;
    enum?: string[];
    default?: unknown;
  }>;
  required?: string[];
}

interface MCPTool {
  name: string;
  description: string;
  inputSchema: MCPInputSchema;
  execute: (params: Record<string, unknown>) => Promise<unknown>;
}

interface MCPOutputSchema {
  type: "object";
  properties: Record<string, {
    type: string;
    description: string;
  }>;
}

interface MCPToolRegistration {
  name: string;
  description: string;
  inputSchema: MCPInputSchema;
  outputSchema?: MCPOutputSchema;
  execute: (params: Record<string, unknown>) => Promise<unknown>;
}

interface MCP {
  registerTool(tool: MCPToolRegistration): Promise<void>;
  unregisterTool(name: string): Promise<void>;
  getTools(): Promise<MCPTool[]>;
}

declare global {
  interface Navigator {
    mcp?: MCP;
  }
}

export type { MCPInputSchema, MCPTool, MCPOutputSchema, MCPToolRegistration, MCP };
