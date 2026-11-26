import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { Converter } from 'opencc-js'

const web = resolve(import.meta.dirname, '..')
const data = resolve(web, 'data')
const read = file => readFileSync(resolve(data, file), 'utf8')
const json = file => JSON.parse(read(file))
const traditionalize = Converter({ from: 'cn', to: 't' })
const simplify = Converter({ from: 't', to: 'cn' })
const readAnnotations = filename => JSON.parse(readFileSync(resolve(web, 'scripts', filename), 'utf8'))
const annotations = {
  ...readAnnotations('analects-annotations.json'),
  ...readAnnotations('dao-annotations.json'),
}
const remainingAnnotations = new Set(Object.keys(annotations))
const annotationTypes = new Set(['典故', '古注', '出处与语境'])
const definitions = json('catalog.json')

const books = definitions.map(({ id, title, book, verses, verseCounts, chapterNames, source }) => {
  const chapters = chapterNames.map((name, index) => ({
    number: index + 1, name, traditional: traditionalize(name), sections: [],
  }))
  const rows = read(`texts/${id}.tsv`).trimEnd().split(/\r?\n/)
  if (rows.length !== verses) throw new Error(`Incomplete work: ${id}`)
  for (const row of rows) {
    const [bookNumber, chapterNumber, sectionNumber, original] = row.split('\t')
    const chapter = chapters[Number(chapterNumber) - 1]
    const section = Number(sectionNumber)
    const key = `${id}:${chapterNumber}:${sectionNumber}`
    const annotation = annotations[key]
    if (Number(bookNumber) !== book || !original || !chapter || section !== chapter.sections.length + 1) {
      throw new Error(`Invalid passage: ${key}`)
    }
    if (!annotation || !remainingAnnotations.has(key) || !annotationTypes.has(annotation.contextType)
      || !Array.isArray(annotation.diagram) || annotation.diagram.length !== 3
      || ![annotation.title, annotation.meaning, annotation.context, annotation.source, ...annotation.diagram]
        .every(value => typeof value === 'string' && value.trim())
      || typeof annotation.sourceUrl !== 'string' || new URL(annotation.sourceUrl).protocol !== 'https:') {
      throw new Error(`Incomplete annotation: ${key}`)
    }
    const traditional = traditionalize(original)
    const simplified = simplify(original)
    if (Array.from(traditional).length !== Array.from(simplified).length) throw new Error(`Unaligned passage: ${key}`)
    chapter.sections.push({ id: key, section, original, traditional, simplified, annotation })
    remainingAnnotations.delete(key)
  }
  if (chapters.length !== verseCounts.length ||
      chapters.some((chapter, index) => chapter.sections.length !== verseCounts[index])) {
    throw new Error(`Incomplete chapter: ${id}`)
  }
  const { noticeFile, ...provenance } = source
  return {
    id, title, traditional: traditionalize(title), source: { ...provenance, notice: read(noticeFile) },
    verses, chapters,
  }
})

if (remainingAnnotations.size) throw new Error(`Unknown annotation keys: ${[...remainingAnnotations]}`)
mkdirSync(resolve(web, 'public'), { recursive: true })
writeFileSync(resolve(web, 'public/corpus.json'), JSON.stringify(books))
console.log(books.map(book => `${book.title} ${book.chapters.length} 篇章 / ${book.verses} 段`).join(' · '))
