<template>
  <div class="coach-shell">
    <header class="coach-header"><a href="/coach" class="brand"><span class="brand-icon">ai</span><span>AI Coach<small>Learning that prepares you for the work</small></span></a>
      <div class="identity">{{ identity?.name }} <a href="/update-password">Account</a><a href="/api/method/logout">Sign out</a></div>
    </header>
    <nav aria-label="Training navigation">
      <button v-for="tab in tabs" :key="tab" :class="{selected: screen === tab}" @click="navigate(tab)">{{ labels[tab] }}</button>
      <a href="/lms/courses">Course catalog ↗</a><a v-if="identity?.staff" href="/lms/batches">Batches ↗</a>
    </nav>
    <p v-if="error" class="alert" role="alert">{{ error }} <button @click="error=''">Dismiss</button></p>
    <p v-if="loading" role="status">Loading your workspace…</p>
    <main v-else-if="data">
      <template v-if="screen === 'learning'">
        <div class="page-title"><div><p class="eyebrow">YOUR LEARNING</p><h1>Ready for your next step?</h1><p>Build confidence, practice the process, and get trainer feedback.</p></div><button @click="refresh">Refresh</button></div>
        <div class="stats"><article><strong>{{ data.assignments.filter(a => !a.completed).length }}</strong><span>To complete</span></article><article><strong>{{ data.assignments.filter(a => a.completed).length }}</strong><span>Completed</span></article><article><strong>{{ data.attempts.filter(a => a.status === 'submitted' && a.mode === 'assessment').length }}</strong><span>Awaiting review</span></article></div>
        <p v-if="!data.assignments.length" class="empty">Your trainer has not assigned any learning yet.</p>
        <div class="cards"><article v-for="a in data.assignments" :key="a.name" class="card">
          <div class="card-top"><span class="pill">{{ a.course ? 'Course' : 'AI simulation' }}</span><span :class="['pill', a.completed ? 'success' : '']">{{ a.completed ? 'Completed' : a.mandatory ? 'Required' : 'Optional' }}</span></div>
          <h2>{{ courseTitle(a.course) || a.scenario_version }}</h2><p v-if="identity.staff">Learner: {{ a.member }}</p><p>{{ a.due_date ? 'Due ' + a.due_date : 'Learn at your pace' }}</p>
          <a v-if="a.course" class="button" :href="'/lms/courses/' + encodeURIComponent(a.course)">Open course</a>
          <div v-for="binding in activities(a)" :key="binding.activity || 'standalone'" class="activity">
            <small v-if="binding.lesson">AI activity in {{ binding.lesson }}</small>
            <div v-for="channel in binding.channels" :key="channel" class="start-row"><span>{{ channel }}</span>
              <button v-for="mode in ['walkthrough','practice','assessment']" :key="mode" :disabled="busy || a.member !== identity.user" @click="start(a, binding, channel, mode)">{{ mode }}</button>
            </div>
          </div>
          <a v-if="a.completed && a.course" class="button secondary" :href="'/lms/courses/' + encodeURIComponent(a.course)">View completion / certificate</a>
        </article></div>
        <h2>Recent attempts</h2><div class="table-wrap"><table><thead><tr><th>Channel</th><th>Mode</th><th>Status</th><th>Score</th><th></th></tr></thead><tbody><tr v-for="a in data.attempts" :key="a.name"><td>{{ a.channel }}</td><td>{{ a.mode }}</td><td>{{ a.status }} / {{ a.grading_status }}</td><td>{{ a.result?.score ?? '—' }}</td><td><button @click="openAttempt(a.name)">Open</button></td></tr></tbody></table></div>
      </template>
      <Builder v-if="screen === 'authoring'" :workspace="data" @changed="refresh" @error="showError" />
      <Operations v-if="screen === 'operations'" :workspace="data" :identity="identity" @changed="refresh" @error="showError" />
      <template v-if="screen === 'reviews'">
        <div class="page-title"><div><p class="eyebrow">TRAINER WORKSPACE</p><h1>Assessment reviews</h1></div><button @click="refresh">Refresh</button></div>
        <div class="cards"><article v-for="a in data.attempts.filter(a => a.mode === 'assessment')" :key="a.name" class="card"><h2>{{ a.member }}</h2><p>{{ a.channel }} · {{ a.status }} · {{ a.result?.score ?? 'Grading' }}</p><button @click="openAttempt(a.name)">Review evidence</button><p v-if="a.grading_error" class="alert">{{ a.grading_error }}</p><button v-if="a.grading_status === 'failed'" @click="retryGrade(a.name)">Retry grading</button></article></div>
      </template>
      <template v-if="screen === 'reports'"><div class="page-title"><h1>Training performance</h1><a class="button" href="/api/method/bpo_coach.api.report?export=1">Download CSV</a></div><div class="stats" v-if="report"><article v-for="(value, key) in report.summary" :key="key"><strong>{{ value === null ? '—' : typeof value === 'number' ? Math.round(value * 10)/10 : value }}</strong><span>{{ key.replaceAll('_', ' ') }}</span></article></div><p>First-attempt metrics count graded assessments only. Trainer approval is reported separately.</p></template>
      <Player v-if="screen === 'attempt' && attempt" :key="attempt.name" :initial="attempt" :identity="identity" @changed="refresh" @error="showError" @close="navigate('learning')" />
    </main>
    <footer>AI Coach · Internal BPO training · {{ identity?.version }}</footer>
  </div>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, parse } from './lib/api'
import Builder from './components/Builder.vue'
import Operations from './components/Operations.vue'
import Player from './components/Player.vue'
const identity=ref(null), data=ref(null), attempt=ref(null), screen=ref('learning'), loading=ref(true), busy=ref(false), error=ref(''), report=ref(null)
const labels={learning:'My learning', authoring:'Scenario studio', operations:'Learning operations', reviews:'Trainer reviews', reports:'Reports'}
const tabs=computed(()=>identity.value?.staff?Object.keys(labels):['learning'])
const showError=e=>{error.value=e?.message || String(e)}
const activities=a=>a.course?parse(a.bindings_json):[{version:a.scenario_version, channels:parse(a.channels_json)}]
const courseTitle=name=>data.value?.courses.find(c=>c.name===name)?.title
async function refresh(){try{data.value=await api('workspace')}catch(e){showError(e)}}
async function navigate(tab){screen.value=tab; history.replaceState(null,'','/coach'); if(tab==='reports')try{report.value=await api('report')}catch(e){showError(e)}}
async function start(a,b,channel,mode){busy.value=true; try{attempt.value=await api('start',{assignment:a.name, scenario_version:b.version,lesson:b.lesson,activity_id:b.activity,channel,mode}); screen.value='attempt';history.replaceState(null,'','/coach?attempt='+encodeURIComponent(attempt.value.name))}catch(e){showError(e)}finally{busy.value=false}}
async function openAttempt(name){try{attempt.value=await api('get_attempt',{name});screen.value='attempt'; history.replaceState(null,'','/coach?attempt='+encodeURIComponent(name))}catch(e){showError(e)}}
async function retryGrade(name){try{await api('retry_grading',{attempt:name});await refresh()}catch(e){showError(e)}}
onMounted(async()=>{try{identity.value=await api('me');await refresh();const q=new URLSearchParams(location.search);if(q.get('attempt'))await openAttempt(q.get('attempt'));else if(q.get('tab') && tabs.value.includes(q.get('tab')))await navigate(q.get('tab'))}catch(e){showError(e)}finally{loading.value=false}})
</script>
