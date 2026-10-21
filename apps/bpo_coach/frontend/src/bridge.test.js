import { describe, expect, it } from 'vitest'
import { AICoach } from './bridge'

describe('native EditorJS bridge', () => {
  it('round-trips an authored version and selected channels', () => {
    const tool = new AICoach({ data: {}, readOnly: false })
    const element = tool.render()
    const input = element.querySelector('input:not([type=checkbox])')
    input.value = '  version-1  '
    input.dispatchEvent(new Event('input'))
    const voice = element.querySelectorAll('[type=checkbox]')[2]
    voice.checked = true
    voice.dispatchEvent(new Event('change'))
    expect(tool.save()).toEqual({ version: 'version-1', channels: ['voice'] })
    expect(tool.validate(tool.save())).toBe(true)
    const reopened = new AICoach({ data: tool.save(), readOnly: false })
    expect(reopened.render().querySelectorAll('[type=checkbox]')[2].checked).toBe(true)
    voice.checked = false
    voice.dispatchEvent(new Event('change'))
    expect(tool.validate(tool.save())).toBe(false)
  })

  it('renders a fixed portal link without exposing authoring controls', () => {
    const tool = new AICoach({ data: { version: '<img src=x onerror=alert(1)>' }, readOnly: true })
    const element = tool.render()
    expect(AICoach.isReadOnlySupported).toBe(true)
    expect(element.querySelector('a').getAttribute('href')).toBe('/coach')
    expect(element.querySelector('input, img, script')).toBeNull()
  })

  it('handles malformed stored data and rejects invalid blocks', () => {
    for (const data of [undefined, null, { version: 7, channels: 'voice' }]) {
      const tool = new AICoach({ data })
      expect(() => tool.render()).not.toThrow()
      expect(tool.validate(tool.save())).toBe(false)
    }
    for (const data of [{ version: ' ', channels: ['voice'] }, { version: 'v', channels: ['bogus'] }, { version: 'v', channels: 'voice' }]) {
      expect(new AICoach({}).validate(data)).toBe(false)
    }
  })

  it('does not mutate EditorJS data or share saved arrays', () => {
    const data = { version: 'v', channels: ['voice', 'voice', 'bogus'] }
    const tool = new AICoach({ data })
    expect(tool.save().channels).toEqual(['voice'])
    tool.save().channels.push('chat')
    expect(tool.save().channels).toEqual(['voice'])
    expect(data.channels).toEqual(['voice', 'voice', 'bogus'])
  })
})
