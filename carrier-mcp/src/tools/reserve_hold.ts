import { z } from 'zod'
import type { AdditionalToolsContext } from '@solvapay/mcp'

/**
 * `reserve_hold`: Nordlink Groupage sells a hold on spare pallet space on trunk NL-417
 * (Daventry hub to the Monza paddock) as a paid MCP tool on SolvaPay.
 *
 * Price: the holding fee, set by the SolvaPay plan on SOLVAPAY_PRODUCT_REF (GBP 60 per hold,
 * created by `node scripts/setup-product.mjs`). SolvaPay handles identity and payment: an
 * unpaid call returns a paywall result (`paywallReason` + checkout link) instead of running
 * this handler; a paid call runs it and gets the booking back.
 *
 * Simulated carrier side: no real truck is booked. The values mirror Nordlink's email in
 * data/carriers/nordlink_groupage_email.txt in the Safety Car app.
 */
const TRUNK = {
  carrier: 'Nordlink Groupage Ltd',
  trunk: 'NL-417',
  space: '1 pallet space (120x80cm, max 150kg)',
  route: 'Daventry hub to Monza circuit paddock gate, 2-driver trunk via Dover-Calais',
  collectionCutoff: '2026-11-24T20:00:00+00:00',
  departure: '2026-11-24T21:00:00+00:00',
  eta: '2026-11-26T09:00:00+01:00',
  holdUntil: '2026-11-24T18:00:00+00:00',
  transportGbp: 340,
  maxKg: 150,
}

function holdRef(shipmentId: string): string {
  const rnd = crypto.getRandomValues(new Uint8Array(2))
  const hex = Array.from(rnd, b => b.toString(16).padStart(2, '0')).join('').toUpperCase()
  return `${TRUNK.trunk}-H-${shipmentId.replace(/[^A-Z0-9]/gi, '').slice(-4).toUpperCase() || 'XXXX'}-${hex}`
}

export function registerReserveHold(ctx: AdditionalToolsContext): void {
  ctx.registerPayable('reserve_hold', {
    title: 'Reserve a backup pallet space on Nordlink trunk NL-417',
    description:
      'Holds 1 pallet space (120x80cm, max 150 kg) on Nordlink trunk NL-417 from the Daventry hub to the Monza ' +
      'circuit paddock (departs Tue 21:00 UK, ETA Thu 09:00 CET) until Tue 18:00 UK. Charges the non-refundable ' +
      'holding fee per call through SolvaPay. Transport (GBP 340) is NOT included: it is billed only if the slot ' +
      'is confirmed. The crate must be on an ATA Carnet or have a commercial invoice by Tue 17:00. If the caller ' +
      'has not paid, the result is a paywall with a checkout link instead of a booking.',
    schema: {
      shipment_id: z.string().min(1).max(40).describe('Buyer shipment reference, e.g. APX-MZA-07'),
      buyer: z.string().min(1).max(80).describe('Buyer company, e.g. Apex Timing Ltd'),
      weight_kg: z.number().positive().max(1000).describe('Crate weight in kg (max 150 per pallet space)'),
      purpose: z.string().max(120).optional().describe("The buying agent's stated purpose"),
    },
    annotations: {
      readOnlyHint: false,
      idempotentHint: false,
      openWorldHint: true,
    },
    handler: async (input, c) => {
      if (input.weight_kg > TRUNK.maxKg) {
        const refused: Record<string, unknown> = {
          ok: false,
          reason: `Crate is ${input.weight_kg} kg; a pallet space takes at most ${TRUNK.maxKg} kg.`,
        }
        return c.respond(refused, { text: 'Hold refused: crate too heavy for one pallet space.' })
      }
      const booking: Record<string, unknown> & { hold_ref: string } = {
        ok: true,
        hold_ref: holdRef(input.shipment_id),
        status: 'held',
        carrier: TRUNK.carrier,
        trunk: TRUNK.trunk,
        space: TRUNK.space,
        route: TRUNK.route,
        shipment_id: input.shipment_id,
        buyer: input.buyer,
        weight_kg: input.weight_kg,
        purpose: input.purpose ?? null,
        held_until: TRUNK.holdUntil,
        collection_cutoff: TRUNK.collectionCutoff,
        departure: TRUNK.departure,
        eta: TRUNK.eta,
        paid_for: `Holding fee: reserves ${TRUNK.space} on ${TRUNK.trunk} until Tue 18:00 UK (non-refundable)`,
        not_included: `Transport GBP ${TRUNK.transportGbp}, billed only if the slot is confirmed`,
        conditions: ['Item on the ATA Carnet, or a commercial invoice sent by Tue 17:00 UK'],
        simulated_carrier: true,
      }
      return c.respond(booking, {
        text:
          `Hold ${booking.hold_ref} confirmed on ${TRUNK.trunk} until Tue 18:00 UK. ` +
          `ETA Monza Thu 09:00 CET if confirmed. Transport GBP ${TRUNK.transportGbp} not included.`,
      })
    },
  })

  ctx.server.registerPrompt(
    'reserve_hold',
    {
      title: 'Reserve a backup pallet on NL-417',
      description: 'Reserve a backup pallet space on Nordlink trunk NL-417 to Monza.',
      argsSchema: { shipment_id: z.string().optional() },
    },
    async ({ shipment_id }) => ({
      messages: [
        {
          role: 'user' as const,
          content: {
            type: 'text' as const,
            text: `Reserve a backup pallet space on NL-417 for shipment ${shipment_id ?? 'APX-MZA-07'} (Apex Timing Ltd, 45 kg, purpose: backup freight for race week).`,
          },
        },
      ],
    }),
  )
}
