import json
import logging
import mimetypes
import os
import unicodedata
from functools import cache
from typing import Annotated, Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from ranking import Ranker, character_mapping
from search_vectors import INDEX, TEXTS, WEB, WORKS, embed, index_fingerprint, read_index

WorkFilter = Literal['all', 'analects', 'tao_te_ching']
LOGGER = logging.getLogger(__name__)


@cache
def documents(work):
    rows = (TEXTS / f'{work}.tsv').read_text(encoding='utf-8').splitlines()
    passages = {}
    for row in rows:
        fields = row.split('\t')
        key = ':'.join(fields[:3])
        passages[key] = (fields[3], fields[4])
    return passages


@cache
def ranker(work):
    return Ranker(work)


@cache
def character_map():
    return str.maketrans(character_mapping())


def section_scores(index, vector):
    keys, vectors = index
    scores = np.clip(vectors @ vector, -1, 1)
    best = {}
    for key, score in zip(keys, scores, strict=True):
        best[key] = max(best.get(key, -1), float(score))
    return best


@cache
def semantic_indexes(_index_modified, _corpus_modified):
    return read_index(index_fingerprint(corpus_path().read_bytes()))


class Search:
    def __init__(self, encode=embed):
        self.encode = encode

    def find(self, raw, work):
        text = unicodedata.normalize('NFKC', raw.strip()).translate(character_map())
        normalized = ''.join(char for char in text.lower() if char.isalnum())
        if not normalized:
            return {'mode': 'empty', 'results': []}
        selected = WORKS if work == 'all' else (work,)
        exact = []
        for book in selected:
            for key, (_, folded) in documents(book).items():
                if normalized in folded:
                    exact.append((book, key, '原文匹配'))
        mode = 'semantic'
        originals = {}
        try:
            indexes = semantic_indexes(INDEX.stat().st_mtime_ns, corpus_path().stat().st_mtime_ns)
            vector = self.encode(text)
            semantic = []
            for book in selected:
                original = section_scores(indexes[book, 'original'], vector)
                meaning = section_scores(indexes[book, 'meaning'], vector)
                originals[book] = original
                candidates = [{'key': key, 'cosine': max(score, meaning[key])} for key, score in original.items()]
                semantic.extend(
                    (match['score'], book, match['key'])
                    for match in ranker(book).rank(raw, candidates, limit=8)
                )
        except Exception:
            LOGGER.warning('Semantic search unavailable', exc_info=True)
            mode = 'literal'
            semantic = []
            originals = {}
        ordered = exact + [
            (book, key, '语义候选')
            for _, book, key in sorted(semantic, key=lambda item: -item[0])
        ]
        results = []
        seen = set()
        for book, key, match in ordered:
            if key in seen:
                continue
            seen.add(key)
            _, chapter, section = key.split(':')
            results.append({
                'id': f'{book}:{chapter}:{section}', 'work': book,
                'chapter': int(chapter), 'section': int(section),
                'excerpt': documents(book)[key][0][:96], 'match': match,
                'similarity': originals.get(book, {}).get(key),
            })
            if len(results) == 8:
                break
        if mode == 'semantic':
            results.sort(key=lambda hit: hit['similarity'] if hit['similarity'] is not None else float('-inf'),
                         reverse=True)
        return {'mode': mode, 'results': results}


DIST = WEB / 'dist'
PRODUCTION = os.getenv('CLASSICS_WEB_DEV', os.getenv('YANJING_WEB_DEV')) != '1' and (DIST / 'index.html').is_file()


def corpus_path():
    return (DIST if PRODUCTION else WEB / 'public') / 'corpus.json'


def corpus():
    path = corpus_path()
    if not path.is_file():
        raise HTTPException(503, '请先运行 pnpm corpus 或 pnpm build。')
    return load_corpus(path, path.stat().st_mtime_ns)


@cache
def load_corpus(path, _modified):
    return json.loads(path.read_text(encoding='utf-8'))


app = FastAPI(title='古籍阅读器')
search = Search()


@app.get('/api/books')
def books():
    return [
        {**{key: value for key, value in book.items() if key != 'chapters'},
         'chapterCount': len(book['chapters'])}
        for book in corpus()
    ]


@app.get('/api/books/{work}')
def book(work: str):
    for entry in corpus():
        if entry['id'] == work:
            return entry
    raise HTTPException(404, '未找到这部典籍。')


@app.get('/api/search')
def find(q: Annotated[str, Query(max_length=200)] = '', work: WorkFilter = 'all'):
    return search.find(q, work)


if PRODUCTION:
    mimetypes.add_type('image/webp', '.webp')
    app.mount('/', StaticFiles(directory=DIST, html=True), name='reader')
