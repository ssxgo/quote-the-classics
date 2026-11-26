import hashlib
import json
import os
import re
import tempfile
import zipfile
from functools import cache
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer
from tokenizers.models import WordPiece
from tokenizers.normalizers import BertNormalizer
from tokenizers.pre_tokenizers import BertPreTokenizer
from tokenizers.processors import BertProcessing

WEB = Path(__file__).resolve().parent
DATA = WEB / 'data'
TEXTS = DATA / 'texts'
INDEX = WEB / '.index/search.npz'
MODEL = DATA / 'model/bge-small-zh-int8.onnx'
VOCAB = DATA / 'model/vocab.txt'
WORKS = ('analects', 'tao_te_ching')
BOOK_CODES = {'analects': 68, 'tao_te_ching': 74}
PREFIX = '为这个句子生成表示以用于检索相关文章：'
DIMENSION = 512
INDEX_VERSION = b'web-bge-original-and-meaning-v2\0'


@cache
def tokenizer():
    result = Tokenizer(WordPiece.from_file(str(VOCAB), unk_token='[UNK]'))
    result.add_special_tokens(['[UNK]', '[SEP]', '[CLS]', '[PAD]', '[MASK]'])
    result.normalizer = BertNormalizer(lowercase=False, strip_accents=False)
    result.pre_tokenizer = BertPreTokenizer()
    result.post_processor = BertProcessing(
        ('[SEP]', result.token_to_id('[SEP]')), ('[CLS]', result.token_to_id('[CLS]')),
    )
    result.enable_truncation(max_length=256)
    return result


def encode_tokens(text):
    return tokenizer().encode(text)


@cache
def model():
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(MODEL), options, providers=['CPUExecutionProvider'])


def encode_passage(text):
    tokens = encode_tokens(text)
    inputs = {
        'input_ids': np.array([tokens.ids], dtype=np.int64),
        'attention_mask': np.array([tokens.attention_mask], dtype=np.int64),
        'token_type_ids': np.array([tokens.type_ids], dtype=np.int64),
    }
    vector = model().run(None, inputs)[0][0, 0]
    norm = np.linalg.norm(vector)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError('Invalid BGE embedding')
    return vector / norm


def embed(text):
    return encode_passage(PREFIX + text)


def passage_windows(text):
    chunks = [text] if len(text) <= 220 else [text[i:i + 200] for i in range(0, len(text), 160)]
    sentences = [part.strip() for part in re.split('[。；！？]', text) if len(part.strip()) >= 8]
    return tuple(dict.fromkeys(chunks + sentences))


def index_fingerprint(corpus_bytes):
    digest = hashlib.sha256(INDEX_VERSION)
    passages = [
        (section['id'], section['original'], section['annotation']['meaning'])
        for book in json.loads(corpus_bytes)
        for chapter in book['chapters']
        for section in chapter['sections']
    ]
    digest.update(hashlib.sha256(json.dumps(passages, ensure_ascii=False).encode('utf-8')).digest())
    for source in (MODEL, VOCAB, *(TEXTS / f'{work}.tsv' for work in WORKS)):
        digest.update(hashlib.sha256(source.read_bytes()).digest())
    return digest.hexdigest()


def existing_hints(work):
    rows = (TEXTS / f'{work}.tsv').read_text(encoding='utf-8').splitlines()
    hints = {}
    for row in rows:
        fields = row.split('\t', 5)
        if len(fields) == 6 and fields[5].strip():
            hints[':'.join(fields[:3])] = fields[5].strip()
    return hints


def build_index():
    contents = (WEB / 'public/corpus.json').read_bytes()
    signature = index_fingerprint(contents)
    try:
        read_index(signature)
        print('BGE search index is up to date.')
        return
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
        pass

    books = json.loads(contents)
    arrays = {'signature': np.array(signature)}
    for book in books:
        work = book['id']
        hints = existing_hints(work)
        for field in ('original', 'meaning'):
            texts, keys = [], []
            for chapter in book['chapters']:
                for section in chapter['sections']:
                    key = f"{BOOK_CODES[work]}:{chapter['number']}:{section['section']}"
                    if field == 'original':
                        windows = passage_windows(section['original'])
                    else:
                        windows = passage_windows(section['annotation']['meaning'])
                        if key in hints:
                            windows = tuple(dict.fromkeys((*windows, *passage_windows(hints[key]))))
                    texts.extend(windows)
                    keys.extend([key] * len(windows))
            arrays[f'{work}_{field}_keys'] = np.array(keys)
            arrays[f'{work}_{field}_vectors'] = np.stack([encode_passage(text) for text in texts])
            print(f'{work} {field}: {len(texts)} segments', flush=True)

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=INDEX.parent, suffix='.npz', delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        np.savez(temporary_path, **arrays)
        os.replace(temporary_path, INDEX)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_index(signature):
    result = {}
    with np.load(INDEX, allow_pickle=False) as archive:
        if archive['signature'].item() != signature:
            raise ValueError('Search index does not match the current model and corpus')
        for work in WORKS:
            for field in ('original', 'meaning'):
                keys = archive[f'{work}_{field}_keys'].tolist()
                vectors = archive[f'{work}_{field}_vectors']
                if not keys or vectors.shape != (len(keys), DIMENSION) or not np.isfinite(vectors).all():
                    raise ValueError(f'Invalid search vectors: {work} {field}')
                result[work, field] = keys, vectors
    return result


if __name__ == '__main__':
    build_index()
