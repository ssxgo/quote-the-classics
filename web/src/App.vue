<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import BookLeaf from './BookLeaf.vue'
import { paginate, pageFor } from './pages.mjs'

const examples = [
  { query: '从复习旧知识得到新的理解', label: '温故知新' },
  { query: '像水一样滋养万物而不争', label: '上善若水' },
  { query: '观点不一样也能彼此尊重、和睦相处', label: '和而不同' },
]
const books = shallowRef([])
const loadError = ref('')
const position = ref({ work: 'analects', chapter: 0, page: 0 })
const pending = ref(null)
const turn = shallowRef(null)
const revealed = ref(0)
const query = ref('')
const scope = ref('all')
const results = ref([])
const selectedHit = shallowRef(null)
const searched = ref(false)
const searching = ref(false)
const searchMode = ref('')
const searchError = ref('')
const sources = ref(null)
const reader = ref(null)
const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
const reduced = ref(motion.matches)
let revealFrame = 0
let turnTimer = 0
let request

const bookById = computed(() => new Map(books.value.map(book => [book.id, book])))
const book = computed(() => bookById.value.get(position.value.work))
const chapter = computed(() => book.value?.chapters[position.value.chapter])
const pages = computed(() => chapter.value ? paginate(chapter.value.sections) : [])
const page = computed(() => pages.value[position.value.page])
const section = computed(() => chapter.value?.sections.find(item => item.id === page.value?.id))
const annotation = computed(() => section.value?.annotation)
const target = computed(() => pending.value ?? position.value)
const targetBook = computed(() => bookById.value.get(target.value.work))
const targetChapter = computed(() => targetBook.value?.chapters[target.value.chapter])
const targetPages = computed(() => {
  const sections = targetChapter.value?.sections
  return sections ? paginate(sections) : []
})
const leafPage = computed(() => turn.value ? targetPages.value[target.value.page] : page.value)
const bookPageCounts = computed(() => book.value?.chapters.map(item => paginate(item.sections).length) ?? [])
const bookPageNumber = computed(() => position.value.page + 1
  + bookPageCounts.value.slice(0, position.value.chapter).reduce((sum, count) => sum + count, 0))
const totalBookPages = computed(() => bookPageCounts.value.reduce((sum, count) => sum + count, 0))
const canBack = computed(() => Boolean(target.value.chapter || target.value.page))
const canForward = computed(() => target.value.page < targetPages.value.length - 1
  || target.value.chapter < (targetBook.value?.chapters.length ?? 0) - 1)
const currentHit = computed(() => selectedHit.value?.id === section.value?.id ? selectedHit.value : null)
const fullPage = computed(() => Array.from(page.value?.traditional ?? '').length)

function revealAll() {
  cancelAnimationFrame(revealFrame)
  revealed.value = fullPage.value
}

function beginReveal() {
  cancelAnimationFrame(revealFrame)
  if (reduced.value) return revealAll()
  revealed.value = 0
  const start = performance.now()
  const duration = Math.min(2000, fullPage.value * 43)
  const tick = now => {
    revealed.value = Math.min(fullPage.value, 1 + Math.floor((now - start) * fullPage.value / duration))
    if (revealed.value < fullPage.value) revealFrame = requestAnimationFrame(tick)
  }
  if (fullPage.value) revealFrame = requestAnimationFrame(tick)
}

function settle() {
  clearTimeout(turnTimer)
  if (pending.value) position.value = pending.value
  pending.value = null
  turn.value = null
  if (selectedHit.value && selectedHit.value.id !== section.value?.id) selectedHit.value = null
  beginReveal()
}

function navigate(next, direction = 1) {
  if (Object.keys(next).every(key => next[key] === target.value[key])) return
  if (!turn.value && page.value && !reduced.value) {
    revealAll()
    turn.value = { title: book.value.traditional, chapter: chapter.value.traditional, page: page.value, direction }
    turnTimer = window.setTimeout(settle, 440)
  }
  pending.value = next
  if (!turn.value || reduced.value) settle()
}

function flip(direction) {
  if (direction < 0 ? !canBack.value : !canForward.value) return
  const current = target.value
  const pageIndex = current.page + direction
  if (pageIndex >= 0 && pageIndex < targetPages.value.length) {
    navigate({ ...current, page: pageIndex }, direction)
    return
  }
  const chapterIndex = current.chapter + direction
  const previous = direction < 0 ? paginate(targetBook.value.chapters[chapterIndex].sections).length - 1 : 0
  navigate({ ...current, chapter: chapterIndex, page: previous }, direction)
}

function selectBook(work) {
  if (target.value.work !== work) navigate({ work, chapter: 0, page: 0 })
}

function selectChapter(index) {
  navigate({ ...target.value, chapter: index, page: 0 }, index < target.value.chapter ? -1 : 1)
}

function openHit(hit) {
  const hitBook = bookById.value.get(hit.work)
  const chapterIndex = hitBook?.chapters.findIndex(item => item.number === hit.chapter) ?? -1
  if (chapterIndex < 0) return
  const hitChapter = hitBook.chapters[chapterIndex]
  const index = pageFor(paginate(hitChapter.sections), hit.id)
  if (index < 0) return
  selectedHit.value = hit
  navigate({ work: hit.work, chapter: chapterIndex, page: index })
  if (window.matchMedia('(max-width: 760px)').matches) {
    reader.value?.scrollIntoView({ behavior: reduced.value ? 'instant' : 'smooth', block: 'start' })
  }
}

function chapterLabel(hit) {
  const name = bookById.value.get(hit.work)?.chapters.find(item => item.number === hit.chapter)?.name
  return hit.work === 'tao_te_ching' ? name : `${name ?? ''} · ${hit.section}`
}

function similarityLabel(similarity) {
  return Number.isFinite(similarity) ? `句意相似度 ${(similarity * 100).toFixed(1)}%` : '相似度暂不可用'
}

function onKeys(event) {
  if (sources.value?.open || event.altKey || event.ctrlKey || event.metaKey
      || event.target.closest?.('input, textarea, select, [contenteditable]')) return
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()
    flip(event.key === 'ArrowLeft' ? -1 : 1)
  }
}

function motionChanged(event) {
  reduced.value = event.matches
  if (reduced.value) {
    if (turn.value) settle()
    else revealAll()
  }
}

function submitOnEnter(event) {
  if (event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  search()
}

async function search(example) {
  if (typeof example === 'string') {
    query.value = example
    scope.value = 'all'
  }
  request?.abort()
  request = new AbortController()
  const active = request
  const text = query.value.trim()
  searched.value = true
  searching.value = Boolean(text)
  searchMode.value = text ? '' : 'empty'
  searchError.value = ''
  results.value = []
  selectedHit.value = null
  if (!text) return
  try {
    const params = new URLSearchParams({ q: text, work: scope.value })
    const response = await fetch(`/api/search?${params}`, { signal: active.signal })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const data = await response.json()
    if (request !== active) return
    results.value = data.results
    searchMode.value = data.mode
  } catch (error) {
    if (request === active && error.name !== 'AbortError') searchError.value = '搜索服务暂时无法连接，仍可通过目录阅读。'
  } finally {
    if (request === active) searching.value = false
  }
}

async function load() {
  loadError.value = ''
  try {
    const response = await fetch('/corpus.json')
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    books.value = await response.json()
    await nextTick()
    beginReveal()
  } catch {
    loadError.value = '典籍数据加载失败。'
  }
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeys)
  motion.addEventListener('change', motionChanged)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeys)
  motion.removeEventListener('change', motionChanged)
  cancelAnimationFrame(revealFrame)
  clearTimeout(turnTimer)
  request?.abort()
})
</script>

<template>
  <header class="masthead">
    <div class="shell topbar">
      <div class="brand"><span class="brand-stamp" aria-hidden="true">典</span>古籍翻阅</div>
      <button class="text-button source-button" type="button" @click="sources.showModal()">版本与来源 <span aria-hidden="true">↗</span></button>
    </div>
  </header>

  <main class="shell">
    <div class="intro">
      <div class="intro-copy">
        <h1>典籍拾读</h1>
      </div>
      <div class="intro-art" aria-hidden="true"></div>
    </div>
    <nav v-if="books.length" class="bookshelf" aria-label="选择典籍">
      <button v-for="item in books" :key="item.id" type="button" :aria-pressed="target.work === item.id"
        @click="selectBook(item.id)">{{ item.title }}</button>
    </nav>

    <div v-if="loadError" class="panel load-message" role="alert">
      {{ loadError }} <button class="text-button" type="button" @click="load">重试</button>
    </div>
    <p v-else-if="!books.length" class="load-message" role="status">正在展开典籍…</p>

    <div v-if="page" class="workspace">
      <section ref="reader" class="reader" aria-labelledby="reader-title">
        <div class="reader-toolbar">
          <h2 id="reader-title">{{ book.title }}</h2>
          <label class="chapter-picker">
            <span>目录</span>
            <select :key="target.work" :value="target.chapter" aria-label="选择篇章" @change="selectChapter(Number($event.target.value))">
              <option v-for="(item, index) in targetBook.chapters" :key="item.number" :value="index">{{ item.name }}</option>
            </select>
          </label>
        </div>

        <div class="book-stage" :aria-busy="Boolean(turn)">
          <BookLeaf :title="targetBook.traditional" :chapter="targetChapter.traditional" :text="leafPage.traditional"
            :visible="turn ? 0 : revealed" :part="leafPage.part" :parts="leafPage.parts" />
          <div v-if="turn" class="turn-sheet" :class="{ backward: turn.direction < 0 }" aria-hidden="true">
            <BookLeaf :title="turn.title" :chapter="turn.chapter" :text="turn.page.traditional"
              :visible="Infinity" :part="turn.page.part" :parts="turn.page.parts" />
          </div>
        </div>

        <div class="reader-footer">
          <button class="page-button" type="button" :disabled="!canBack" @click="flip(-1)">← <span>上一页</span></button>
          <div class="pagination">
            <span aria-live="polite">第 {{ bookPageNumber }} / {{ totalBookPages }} 页</span>
            <button class="text-button reveal-button" type="button" :disabled="revealed >= fullPage || Boolean(turn)"
              @click="revealAll">立即显示全文</button>
          </div>
          <button class="page-button" type="button" :disabled="!canForward" @click="flip(1)"><span>下一页</span> →</button>
        </div>
      </section>

      <section class="panel search-panel" aria-labelledby="search-title">
        <h2 id="search-title">我说话引经据典！</h2>
        <form class="search-form" @submit.prevent="search()">
          <label class="visually-hidden" for="query">输入想查找的白话或原句</label>
          <textarea id="query" v-model="query" maxlength="200" rows="2"
            placeholder="例如，像水一样滋养万物而不争" @keydown.enter.exact="submitOnEnter"></textarea>
          <div class="search-actions">
            <select v-model="scope" aria-label="搜索范围">
              <option value="all">两书全文</option>
              <option v-for="item in books" :key="item.id" :value="item.id">{{ item.title }}</option>
            </select>
            <button class="primary" type="submit">{{ searching ? '查找中…' : '查找原文 →' }}</button>
          </div>
        </form>
        <div v-if="!searched" class="examples">
          <span>试试</span>
          <button v-for="example in examples" :key="example.label" type="button" :aria-label="`试试：${example.query}`"
            @click="search(example.query)">{{ example.label }}</button>
        </div>
        <div v-else class="results" :aria-busy="searching">
          <p v-if="searching" class="muted" role="status">正在查找相关章句…</p>
          <p v-else-if="searchError" class="muted" role="status">{{ searchError }}</p>
          <template v-else>
            <p v-if="searchMode === 'literal'" class="muted" role="status">句意检索暂不可用，当前按原文字词查找。</p>
            <p v-if="!results.length" class="muted" role="status">{{ searchMode === 'empty' ? '请输入白话或原句。' : '当前范围内没有找到相关章句。' }}</p>
            <p v-else class="results-title" role="status">返回 {{ results.length }} 条候选章句 <span v-if="!currentHit">· 选择一条翻到原文</span></p>
            <ul v-if="results.length" class="result-list">
              <li v-for="hit in results" :key="hit.id">
                <button type="button" :aria-current="currentHit?.id === hit.id ? 'true' : undefined" @click="openHit(hit)">
                  <span class="result-label">
                    <strong>{{ bookById.get(hit.work).title }} · {{ chapterLabel(hit) }}</strong>
                    <span class="result-metadata"><span>{{ hit.match }}</span><span class="similarity">{{ similarityLabel(hit.similarity) }}</span></span>
                  </span>
                  <span class="result-excerpt">{{ hit.excerpt }}</span>
                </button>
              </li>
            </ul>
            <p v-if="results.length" class="similarity-note">百分比为 BGE 余弦相似度，不代表匹配准确率。</p>
          </template>
        </div>
      </section>

      <div class="reading-notes">
        <section class="transcript" aria-labelledby="transcript-title">
          <div class="section-heading">
            <h2 id="transcript-title">简体原文</h2>
            <span class="transcript-meta">
              <span>{{ chapter.name }}<template v-if="book.id !== 'tao_te_ching'"> · {{ section.section }}</template><template v-if="page.parts > 1">（{{ page.part }}/{{ page.parts }}）</template></span>
              <span v-if="currentHit" class="similarity">{{ similarityLabel(currentHit.similarity) }}</span>
            </span>
          </div>
          <p>{{ page.simplified }}</p>
        </section>

        <section class="annotation" aria-labelledby="annotation-title">
          <div class="section-heading">
            <h2 id="annotation-title">释读</h2>
            <span class="annotation-title">{{ annotation.title }}</span>
          </div>
          <p class="meaning">{{ annotation.meaning }}</p>
          <figure class="diagram">
            <figcaption>文意</figcaption>
            <ol><li v-for="step in annotation.diagram" :key="step">{{ step }}</li></ol>
          </figure>
          <h3>{{ annotation.contextType }}</h3>
          <p>{{ annotation.context }}</p>
          <p class="annotation-source">出处 · <a :href="annotation.sourceUrl" target="_blank" rel="noopener">{{ annotation.source }} <span aria-hidden="true">↗</span></a></p>
        </section>
      </div>
    </div>

    <dialog ref="sources" class="source-dialog" aria-labelledby="source-title">
      <form method="dialog" class="section-heading">
        <h2 id="source-title">版本与来源</h2>
        <button class="text-button" type="submit" autofocus>关闭</button>
      </form>
      <p>两部典籍均收录全文，正文与篇章编号沿用所附版本。繁简字形由 OpenCC 转换，释读与示意为本网页编写，篇章注释附有出处链接。</p>
      <details v-for="item in books" :key="item.id">
        <summary>{{ item.title }} · {{ item.source.license }}</summary>
        <p>{{ item.source.name }} · <a :href="item.source.url" target="_blank" rel="noopener">固定版本原始数据 ↗</a></p>
        <p class="revision">{{ item.source.revision }}</p>
        <pre>{{ item.source.notice }}</pre>
      </details>
      <p><a href="https://theme.npm.edu.tw/exh114/TwoHundredTreasures/" target="_blank" rel="noopener">版式参考 · 皕宋——故宫宋版图书观止 ↗</a></p>
      <p><a href="https://www.metmuseum.org/art/collection/search/39915" target="_blank" rel="noopener">题图 · 传屈鼎《夏山图》，大都会艺术博物馆（公版）↗</a></p>
    </dialog>
  </main>
</template>
