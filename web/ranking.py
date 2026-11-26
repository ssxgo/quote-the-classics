import json
import math
import re
import unicodedata
from collections import Counter
from functools import cache

from search_vectors import DATA, TEXTS

STOP = set('的了是我你他她它们在有和与及就也都这那吗呢吧啊呀不着把被个地得为以而其之乎者也要能会应该不能一个自己别人什么怎么为什么是否时候')


@cache
def character_mapping():
    return dict(line.split('\t') for line in (DATA / 't2s.tsv').read_text(encoding='utf-8').splitlines())


class Ranker:
    """Combine BGE similarity with word and concept overlap."""

    def __init__(self, work):
        self.mapping = character_mapping()
        self.groups = [
            line.split('|') for line in (DATA / 'concepts.txt').read_text(encoding='utf-8').splitlines()
            if line and not line.startswith('#')
        ]
        self.terms = {term: group[0] for group in self.groups for term in group}
        self.term_pattern = re.compile('|'.join(re.escape(term) for term in sorted(self.terms, key=lambda term: -len(term))))
        hints = json.loads((DATA / 'expression-hints.json').read_text(encoding='utf-8'))
        self.documents = {}
        frequencies = Counter()
        for line in (TEXTS / f'{work}.tsv').read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):
                continue
            row = line.split('\t')
            key = ':'.join(row[:3])
            texts = row[3:4] + row[5:6] + hints.get(key, [])
            windows = []
            for text in texts:
                normalized = self.normalize(text)
                windows.extend(normalized[i:i + 180] for i in range(0, len(normalized), 120))
            self.documents[key] = [(self.fold(text), self.concepts(text)) for text in windows]
            frequencies.update(set(''.join(text for text, _ in self.documents[key])))
        self.idf = {
            char: math.log(1 + len(self.documents) / (1 + count))
            for char, count in frequencies.items()
        }
        self.unseen = math.log(1 + len(self.documents))

    def normalize(self, text):
        return ''.join(
            self.mapping.get(char, char).lower()
            for char in unicodedata.normalize('NFKC', text) if char.isalnum()
        )

    def fold(self, text):
        return self.term_pattern.sub(lambda match: self.terms[match[0]], text)

    def concepts(self, text):
        return {i for i, group in enumerate(self.groups) if any(term in text for term in group)}

    def query(self, raw):
        normalized = self.normalize(raw)
        folded = self.fold(normalized)
        chars = set(folded) - STOP
        grams = {
            folded[i:i + 2] for i in range(len(folded) - 1)
            if any(char not in STOP for char in folded[i:i + 2])
        }
        weights = {char: self.idf.get(char, self.unseen) for char in chars}
        gram_weights = {gram: sum(self.idf.get(char, self.unseen) for char in gram) / 2 for gram in grams}
        return weights, gram_weights, self.concepts(normalized)

    def evidence(self, query, key):
        chars, grams, concepts = query
        best = 0
        char_total = max(sum(chars.values()), 1e-9)
        gram_total = max(sum(grams.values()), 1e-9)
        for text, document_concepts in self.documents[key]:
            char_coverage = sum(weight for char, weight in chars.items() if char in text) / char_total
            gram_coverage = sum(weight for gram, weight in grams.items() if gram in text) / gram_total
            concept_coverage = len(concepts & document_concepts) / max(len(concepts), 1)
            best = max(best, 0.08 * char_coverage + 0.13 * gram_coverage + 0.12 * concept_coverage)
        return best

    def rank(self, raw, candidates, limit):
        query = self.query(raw)
        scored = [
            {**candidate, 'score': candidate['cosine'] + 0.5 * self.evidence(query, candidate['key'])}
            for candidate in candidates if candidate['key'] in self.documents
        ]
        scored.sort(key=lambda candidate: (-candidate['score'], candidate['key']))
        return scored[:limit]
