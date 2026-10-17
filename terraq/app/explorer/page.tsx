// Thin route file. All Explorer code lives in terraq/explorer/.

import { ExplorerShell } from '@/explorer/components/ExplorerShell'

export const metadata = {
  title: 'Explorer — TerraQ',
  description: 'Mineral exploration console over live Sentinel-2 data',
}

export default function ExplorerPage() {
  return <ExplorerShell />
}
