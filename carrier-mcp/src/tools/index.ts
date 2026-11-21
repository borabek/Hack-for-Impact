import type { AdditionalToolsContext } from '@solvapay/mcp'
import type { Env } from '../worker'
import { registerReserveHold } from './reserve_hold'

export function registerTools(ctx: AdditionalToolsContext, _env: Env): void {
  registerReserveHold(ctx)
}
