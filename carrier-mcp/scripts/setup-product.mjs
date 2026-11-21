#!/usr/bin/env node
// One-off: create Nordlink's "NL-417 holding fee" product + a £60-per-hold plan in the SolvaPay
// sandbox, then write SOLVAPAY_PRODUCT_REF into .env. Re-running reuses an existing product.
//   node scripts/setup-product.mjs [--fee 60]
import { readFileSync, writeFileSync } from 'node:fs'
import { createSolvaPay } from '@solvapay/server'

const ENV_PATH = new URL('../.env', import.meta.url)
const env = Object.fromEntries(
  readFileSync(ENV_PATH, 'utf8').split('\n').filter(l => /^[A-Z_]+=/.test(l)).map(l => {
    const i = l.indexOf('=')
    return [l.slice(0, i), l.slice(i + 1)]
  }),
)
const apiKey = env.SOLVAPAY_SECRET_KEY
if (!apiKey?.startsWith('sk_sandbox_')) {
  console.error('SOLVAPAY_SECRET_KEY must be a sandbox key (sk_sandbox_…) in carrier-mcp/.env')
  process.exit(1)
}
const feeArg = process.argv.indexOf('--fee')
const feeGbp = feeArg > -1 ? Number(process.argv[feeArg + 1]) : 60
const NAME = 'Nordlink NL-417 backup pallet hold'

const sp = createSolvaPay({ apiKey, apiBaseUrl: env.SOLVAPAY_API_BASE_URL || 'https://api.solvapay.com' })
const api = sp.apiClient

const existing = (await api.listProducts?.()) ?? []
const list = Array.isArray(existing) ? existing : existing.products ?? existing.data ?? []
let product = list.find(p => p.name === NAME)
if (product) {
  console.log(`Reusing product ${product.reference ?? product.productRef ?? product.ref}`)
} else {
  product = await api.createProduct({
    name: NAME,
    description:
      'Holds 1 pallet space (120x80cm, max 150kg) on trunk NL-417, Daventry hub to Monza paddock, until Tue 18:00 UK. ' +
      'Non-refundable holding fee. Transport (GBP 340) is billed only if the slot is confirmed.',
    isMcpPay: true,
    metadata: { carrier: 'Nordlink Groupage Ltd', trunk: 'NL-417', demo: 'Safety Car, Hack for Impact' },
  })
  console.log('Created product:', JSON.stringify(product, null, 2))
}
const productRef = product.reference ?? product.productRef ?? product.ref
if (!productRef) throw new Error('No product ref in response: ' + JSON.stringify(product))

const plans = (await api.listPlans?.(productRef)) ?? []
if (plans.length) {
  console.log('Existing plans:', plans.map(p => `${p.reference ?? p.planRef} ${p.name}`).join(', '))
} else {
  const plan = await api.createPlan({
    productRef,
    name: `Holding fee GBP ${feeGbp}`,
    description: 'Pay per hold: one reserve_hold call reserves the slot.',
    currency: 'GBP',
    options: [{ kind: 'charge', amountMinor: Math.round(feeGbp * 100), currency: 'GBP', per: 'unit', meter: 'requests', label: 'per hold' }],
  })
  console.log('Created plan:', JSON.stringify(plan, null, 2))
}

const envText = readFileSync(ENV_PATH, 'utf8').replace(/^SOLVAPAY_PRODUCT_REF=.*$/m, `SOLVAPAY_PRODUCT_REF=${productRef}`)
writeFileSync(ENV_PATH, envText)
console.log(`SOLVAPAY_PRODUCT_REF=${productRef} written to carrier-mcp/.env`)
