import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { paginate, pageFor } from '../src/pages.mjs'

test('parallel pages reassemble long paragraphs and preserve Unicode characters', () => {
  const original = '學而時習之，𠮷。'.repeat(30)
  const simplified = original.replaceAll('學', '学').replaceAll('習', '习')
  const pages = paginate([{ id: 'analects:1:1', traditional: original, simplified }])
  assert.ok(pages.length > 2)
  assert.equal(pages.map(page => page.traditional).join(''), original)
  assert.equal(pages.map(page => page.simplified).join(''), simplified)
  assert.ok(pages.every(page => Array.from(page.traditional).length <= 96))
  assert.equal(pageFor(pages, 'analects:1:1'), 0)
})

test('each chapter section begins on a separately addressable page', () => {
  const pages = paginate(['甲', '乙'].map((text, index) => ({
    id: `analects:1:${index + 1}`, traditional: text, simplified: text,
  })))
  assert.equal(pageFor(pages, 'analects:1:2'), 1)
  assert.equal(pageFor(pages, 'analects:2:1'), -1)
})

test('both books retain all 593 original passages and have complete sourced annotation', () => {
  const corpus = JSON.parse(readFileSync(new URL('../public/corpus.json', import.meta.url)))
  assert.deepEqual(corpus.map(book => [book.id, book.chapters.length, book.verses]), [
    ['analects', 20, 512], ['tao_te_ching', 81, 81],
  ])
  for (const book of corpus) {
    const source = new URL(`../../app/src/main/assets/bibles/${book.id}.tsv`, import.meta.url)
    const rows = readFileSync(source, 'utf8').trimEnd().split(/\r?\n/).map(row => row.split('\t'))
    const sections = book.chapters.flatMap(chapter => chapter.sections)
    assert.ok(book.chapters.every(chapter => chapter.sections.length > 0))
    assert.ok(sections.every(({ annotation }) => annotation?.meaning && annotation.context
      && annotation.source && annotation.sourceUrl.startsWith('https://') && annotation.diagram.length === 3))
    assert.deepEqual(sections.map(section => [section.id, section.original]),
      rows.map(([, chapter, section, original]) => [`${book.id}:${chapter}:${section}`, original]))
    for (const chapter of book.chapters) {
      const pages = paginate(chapter.sections)
      assert.ok(pages.every(page => Array.from(page.traditional).length <= 96))
      for (const script of ['traditional', 'simplified']) {
        assert.equal(pages.map(page => page[script]).join(''), chapter.sections.map(section => section[script]).join(''))
      }
    }
  }
})
