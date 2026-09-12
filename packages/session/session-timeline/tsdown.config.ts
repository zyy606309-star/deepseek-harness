import { clientBundle } from '../../client/tsdown.client.ts'

export default clientBundle(
  '@deepseek-ai/dsh-session-timeline',
  ['lib/types/index.js'],
  { hostPhase: true },
)
