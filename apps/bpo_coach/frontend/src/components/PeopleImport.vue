<template>
  <form class="card" @submit.prevent="submit">
    <h2>People &amp; access: import CSV</h2>
    <p>Create or update up to 100 people by email. Existing emails update names and, when supplied, roles. New emails create accounts.</p>
    <p>Headers: <code>name,email,password,role,batchIds</code>. New accounts require a password of 12–128 characters. Leave password blank for existing people. Roles are learner, trainer or admin; blank preserves an existing role or defaults to learner.</p>
    <p v-if="!identity.admin">Trainers can import learners only. New learners need a batch in your assigned processes where you are an instructor or evaluator. Existing learners must belong entirely to your assigned processes.</p>
    <p>Separate batch IDs with semicolons. Imports add memberships and preserve existing ones. Existing assignments do not automatically include new members.</p>
    <a :href="template" download="people-template.csv">Download CSV template</a>
    <details v-if="batches.length"><summary>Available batch IDs</summary><ul><li v-for="batch in batches" :key="batch.name">{{ batch.title }}: <code>{{ batch.name }}</code></li></ul></details>
    <label>CSV file<input ref="fileInput" type="file" accept=".csv,text/csv" :disabled="busy || reading" @change="load"></label>
    <p v-if="filename && !result" role="status">{{ filename }} ready to import. Each row will be validated before saving.</p>
    <p v-if="error" role="alert" class="alert">{{ error }}</p>
    <div v-if="result" role="status">
      <p>{{ result.created }} created, {{ result.updated }} updated, {{ result.errors.length }} failed.</p>
      <ul v-if="result.errors.length"><li v-for="entry in result.errors" :key="entry.row">Row {{ entry.row }} ({{ entry.email }}): {{ entry.message }}</li></ul>
    </div>
    <button :disabled="!csv || busy || reading">{{ busy ? 'Importing…' : 'Import people' }}</button>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../lib/api'

defineProps({ identity: { type: Object, required: true }, batches: { type: Array, default: () => [] } })
const emit = defineEmits(['changed'])
const csv = ref(''), filename = ref(''), error = ref(''), result = ref(null)
const busy = ref(false), reading = ref(false), fileInput = ref(null)
const template = 'data:text/csv;charset=utf-8,' + encodeURIComponent('name,email,password,role,batchIds\r\nExample Person,person@example.com,ReplaceWith12PlusChars,learner,\r\n')

async function load(event) {
  csv.value = ''; filename.value = ''; error.value = ''; result.value = null
  const file = event.target.files?.[0]
  if (!file) return
  reading.value = true
  try {
    if (file.size > 500_000) throw new Error('CSV must be smaller than 500 KB.')
    const text = await file.text()
    if (!text.trim()) throw new Error('Choose a CSV containing people to import.')
    csv.value = text; filename.value = file.name
  } catch (e) { error.value = e.message || 'Could not read this CSV.' }
  finally { reading.value = false }
}

async function submit() {
  if (busy.value || !csv.value) return
  busy.value = true; error.value = ''; result.value = null
  try {
    result.value = await api('import_people', { csv_text: csv.value }, 'bpo_coach.people_import')
    csv.value = ''; filename.value = ''; fileInput.value.value = ''
    emit('changed')
  } catch (e) { error.value = e.message || 'Import failed. Please retry.' }
  finally { busy.value = false }
}
</script>
