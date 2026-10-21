import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { resolve } from 'node:path'
const pilot = resolve(process.argv[2] || '../..')
const engine = await import(pathToFileURL(resolve(pilot, 'src/shared/engine.ts')))
const source = readFileSync(resolve(pilot, 'tests/engine.test.ts'), 'utf8')
const literal = source.match(/const scenario: ScenarioContent = ([\s\S]*?);\r?\nconst event/)[1]
// The checked-in pilot's test fixture is a plain object literal, not external input.
const { runInNewContext } = await import('node:vm')
const scenario = runInNewContext('(' + literal + ')')
let seed = 91483
function random() { seed = (1664525 * seed + 1013904223) >>> 0; return seed / 2 ** 32 }
const cases = []
for (let i = 0; i < 160; i++) {
  const events = Array.from({length: Math.floor(random() * 8)}, (_, j) => {
    const wrong = random() < .4
    return {id: 'event-' + j, request_id: 'request-' + j, step_id: 'verify', hotspot_id: wrong ? 'pay' : 'input', value: 'INV-1048', correct: Number(!wrong), critical: Number(wrong && random() < .7), created_at: 1000 + j}
  })
  const objective = engine.objectiveResults(scenario, events)
  const s = structuredClone(scenario)
  s.rubric.forEach(r => {r.weight = 1 + Math.floor(random() * 10)})
  const criteria = objective.map(c => ({...c, score: random() < .4 ? c.score : Math.floor(random() * 101)}))
  cases.push({scenario:s,events,objective,completed:engine.completedStep(s,0,events),criteria,
    assessment:engine.aggregateAssessment(s,criteria,1000,2500,[],[]),
    validEvidence:engine.validateEvidence(criteria,events,[])})
}
const fixture = {source:'AI Coach pilot src/shared/engine.ts', scenario, cases,
  normalization:['  ＩＮＶ-1048  ','A\u00a0 B','İ Σ ΟΣ ß','\ufeffAbC\ufeff','one\u2028two'].map(value=>({value,expected:engine.normalizeAnswer(value)})),
  redaction:['walkthrough','practice','assessment'].map(mode=>({mode,result:engine.sanitizeScenario(scenario,mode,3)})),
  actions:['INV-1048',' inv-1048 ','wrong',''].map(value=>({value,result:engine.validateAction(scenario,0,'input',value)}))}
writeFileSync(resolve('apps/bpo_coach/tests/parity.json'), JSON.stringify(fixture,null,2)+'\n')
console.log(`Generated ${cases.length} scoring parity cases from the existing pilot.`)
