/* SPDX-License-Identifier: MPL-2.0 */

import { describe, expect, it } from 'vitest'
import { useSolarisStore } from './useSolarisStore'

describe('useSolarisStore', () => {
  it('updates scope fields and divergence state', () => {
    useSolarisStore.setState({
      scope: { tenant: 'personal', namespace: 'solaris', workspace: 'default', project: 'default' },
      showDivergence: true,
    })

    useSolarisStore.getState().setScopeField('project', 'graph')
    expect(useSolarisStore.getState().scope.project).toBe('graph')

    useSolarisStore.getState().toggleDivergence()
    expect(useSolarisStore.getState().showDivergence).toBe(false)
  })
})
