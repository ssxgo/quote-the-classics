import unittest

from search_vectors import encode_passage, encode_tokens, embed, passage_windows
from server import Search


class SearchTest(unittest.TestCase):
    def test_tokenizer_matches_reference_fixtures(self):
        import json
        from search_vectors import WEB

        path = WEB / 'test/tokenizer-fixtures.json'
        for fixture in json.loads(path.read_text(encoding='utf-8')):
            self.assertEqual(encode_tokens(fixture['text']).ids, fixture['ids'])

    def test_exact_match_works_with_unavailable_model(self):
        def unavailable(_):
            raise RuntimeError('offline test')

        search = Search(encode=unavailable)
        with self.assertLogs('server', level='WARNING'):
            response = search.find('溫故而知新', 'analects')
            self.assertEqual(search.find('溫故而知新', 'tao_te_ching')['results'], [])
        self.assertEqual(response['mode'], 'literal')
        self.assertEqual(response['results'][0]['id'], 'analects:2:11')
        self.assertIsNone(response['results'][0]['similarity'])
        self.assertEqual(search.find('?!', 'all')['results'], [])

    def test_paraphrases_reach_the_intended_passages(self):
        search = Search()
        for query, work, target in [
            ('从复习旧知识得到新的理解', 'analects', 'analects:2:11'),
            ('像水一样滋养万物而不争', 'tao_te_ching', 'tao_te_ching:8:1'),
            ('遇到别人身上的缺点应该反省自己', 'all', 'analects:4:17'),
            ('三个人一起走，每个人都有值得学习的地方', 'all', 'analects:7:22'),
            ('欢迎远道而来的朋友', 'all', 'analects:1:1'),
            ('祸和福会互相转化', 'all', 'tao_te_ching:58:1'),
            ('自己不愿意的事不要强加给别人', 'all', 'analects:12:2'),
            ('能够了解别人很聪明，了解自己才是明智', 'tao_te_ching', 'tao_te_ching:33:1'),
        ]:
            with self.subTest(query=query):
                response = search.find(query, work)
                self.assertEqual(response['mode'], 'semantic')
                self.assertIn(target, [hit['id'] for hit in response['results'][:3]])

    def test_full_catalog_and_original_similarity(self):
        from server import WORKS, documents
        import numpy as np
        import unicodedata

        self.assertEqual(WORKS, ('analects', 'tao_te_ching'))
        self.assertEqual([len(documents(work)) for work in WORKS], [512, 81])
        response = Search().find('己所不欲，勿施于人', 'analects')
        hit = response['results'][0]
        self.assertEqual(hit['id'], 'analects:12:2')
        self.assertEqual(hit['match'], '原文匹配')
        query = embed(unicodedata.normalize('NFKC', '己所不欲，勿施于人'))
        original = documents('analects')['68:12:2'][0]
        expected = max(float(np.dot(query, encode_passage(window))) for window in passage_windows(original))
        self.assertAlmostEqual(hit['similarity'], expected, places=5)

    def test_low_similarity_queries_still_show_ranked_candidates(self):
        search = Search()
        for query in ['Python 怎么读取 CSV 文件', '明天航班几点起飞', 'zxqv7921', '吃牛肉', '显卡', '天气']:
            with self.subTest(query=query):
                response = search.find(query, 'all')
                self.assertEqual(response['mode'], 'semantic')
                self.assertEqual(len(response['results']), 8)
                self.assertTrue(all(hit['similarity'] is not None for hit in response['results']))

    def test_short_hunger_queries_find_the_relevant_original(self):
        search = Search()
        for query in ['饥饿', '挨饿']:
            with self.subTest(query=query):
                results = search.find(query, 'all')['results']
                self.assertEqual(results[0]['id'], 'tao_te_ching:75:1')
                self.assertEqual(results[0]['match'], '语义候选')
                self.assertIsNotNone(results[0]['similarity'])
                self.assertTrue(all(hit['work'] == 'analects' for hit in search.find(query, 'analects')['results']))

    def test_candidates_are_sorted_by_displayed_original_similarity(self):
        search = Search()
        for query in ['饥饿', '己所不欲，勿施于人', '从复习旧知识得到新的理解']:
            with self.subTest(query=query):
                results = search.find(query, 'all')['results']
                self.assertEqual(len(results), 8)
                similarities = [hit['similarity'] for hit in results]
                self.assertEqual(similarities, sorted(similarities, reverse=True))

    def test_paraphrase_can_surface_a_lower_scoring_original(self):
        results = Search().find('从眼前的小事做起', 'all')['results']
        hit = next(hit for hit in results if hit['id'] == 'tao_te_ching:64:1')
        self.assertLess(hit['similarity'], results[0]['similarity'])
