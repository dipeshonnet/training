import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PeopleImport from './components/PeopleImport.vue'
import { api } from './lib/api'

vi.mock('./lib/api', () => ({ api: vi.fn() }))

function component(admin = false) {
  return mount(PeopleImport, { props: { identity: { staff: true, admin }, batches: [{ name: 'batch-1', title: 'Training batch' }] } })
}
async function choose(wrapper, text = 'name,email\nExample,example@example.test', size = 40) {
  Object.defineProperty(wrapper.get('input[type=file]').element, 'files', {
    configurable: true, value: [{ name: 'people.csv', size, text: async () => text }],
  })
  await wrapper.get('input').trigger('change')
  await flushPromises()
}
beforeEach(() => vi.clearAllMocks())

describe('People CSV import', () => {
  it('provides a template, batch references and trainer scope guidance', () => {
    const wrapper = component()
    expect(wrapper.get('a').attributes('download')).toBe('people-template.csv')
    expect(wrapper.text()).toContain('batch-1')
    expect(wrapper.text()).toContain('Trainers can import learners only')
    expect(wrapper.get('button').element.disabled).toBe(true)
    wrapper.unmount()
  })
  it('submits to the scoped endpoint, shows row results and refreshes the workspace', async () => {
    api.mockResolvedValue({ created: 1, updated: 0, errors: [{ row: 3, email: 'bad@example.test', message: 'Invalid role.' }] })
    const wrapper = component(true)
    await choose(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api).toHaveBeenCalledWith('import_people', { csv_text: 'name,email\nExample,example@example.test' }, 'bpo_coach.people_import')
    expect(wrapper.text()).toContain('1 created, 0 updated, 1 failed')
    expect(wrapper.text()).toContain('Row 3 (bad@example.test): Invalid role.')
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(wrapper.get('button').element.disabled).toBe(true)
    wrapper.unmount()
  })
  it('blocks oversized files before reading and keeps failed requests retryable', async () => {
    const wrapper = component()
    await choose(wrapper, 'data', 500_001)
    expect(wrapper.get('[role=alert]').text()).toContain('500 KB')
    expect(wrapper.get('button').element.disabled).toBe(true)
    await choose(wrapper)
    api.mockRejectedValue(new Error('Malformed CSV.'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toBe('Malformed CSV.')
    expect(wrapper.get('button').element.disabled).toBe(false)
    wrapper.unmount()
  })
})
