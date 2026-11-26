const LIMIT = 96
const SENTENCE_END = /[。！？；]/
const CLOSING = /[”’」』）》】]/

export function paginate(sections) {
  return sections.flatMap(section => {
    const traditional = Array.from(section.traditional)
    const simplified = Array.from(section.simplified)
    if (traditional.length !== simplified.length) throw new Error(`Unaligned text: ${section.id}`)
    const pages = []
    for (let start = 0; start < traditional.length;) {
      let end = Math.min(start + LIMIT, traditional.length)
      if (end < traditional.length) {
        for (let boundary = end - 1; boundary >= start + LIMIT / 2; boundary--) {
          if (!SENTENCE_END.test(traditional[boundary])) continue
          let after = boundary + 1
          while (CLOSING.test(traditional[after] ?? '')) after++
          if (after > end) continue
          end = after
          break
        }
      }
      pages.push({
        id: section.id,
        part: pages.length + 1,
        traditional: traditional.slice(start, end).join(''),
        simplified: simplified.slice(start, end).join(''),
      })
      start = end
    }
    return pages.map(page => ({ ...page, parts: pages.length }))
  })
}

export function pageFor(pages, id) {
  return pages.findIndex(page => page.id === id)
}
