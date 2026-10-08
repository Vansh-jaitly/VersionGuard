import unittest

from versionguard.store import ApiDoc, Bm25Retriever, corpus_fingerprint, diversify, format_docs, tokenize

DOCS = [
    ApiDoc("minilib.rolling_mean", "function", "(values, size)", "Return the mean over a sliding window."),
    ApiDoc("minilib.scale", "function", "(values, by=1.0)", "Multiply every value by a factor."),
    ApiDoc("minilib.Table.count", "method", "(self)", "Return the number of rows."),
    ApiDoc("minilib.concat", "function", "(tables)", "Join several Table objects into one."),
]


class StoreTests(unittest.TestCase):
    def test_tokenize_splits_names(self):
        self.assertEqual(tokenize("pandas.DataFrame.to_csv"), ["pandas", "data", "frame", "to", "csv"])
        self.assertEqual(tokenize("rolling_mean(x)"), ["rolling", "mean"])

    def test_bm25_finds_the_obvious_entry(self):
        retriever = Bm25Retriever(DOCS)
        self.assertEqual(retriever.search("average over a sliding window", 1)[0][0].qualname, "minilib.rolling_mean")
        self.assertEqual(retriever.search("join tables", 1)[0][0].qualname, "minilib.concat")
        self.assertEqual(retriever.search("zzz qqq", 3), [])
        self.assertEqual(Bm25Retriever([]).search("anything", 3), [])

    def test_bm25_is_deterministic(self):
        first = [d.qualname for d, _ in Bm25Retriever(DOCS).search("return the table rows mean", 4)]
        second = [d.qualname for d, _ in Bm25Retriever(list(DOCS)).search("return the table rows mean", 4)]
        self.assertEqual(first, second)

    def test_one_entry_per_function_name(self):
        # The real case that prompted this: three copies of numpy's any()/all().
        hits = [(ApiDoc(name), 1.0) for name in (
            "numpy.ndarray.all", "numpy.matrix.any", "numpy.ndarray.any", "numpy.any", "numpy.all", "numpy.sum")]
        self.assertEqual([d.qualname for d, _ in diversify(hits, 3)], ["numpy.all", "numpy.any", "numpy.sum"])
        self.assertEqual(diversify([], 3), [])
        self.assertEqual(len(diversify(hits, 1)), 1)

    def test_format_docs_respects_budget(self):
        long = [ApiDoc(f"lib.f{i}", "function", "(x)", "word " * 400) for i in range(3)]
        text = format_docs(long, budget=600)
        self.assertLessEqual(len(text), 600)
        for i in range(3):
            self.assertIn(f"lib.f{i}(x)", text)   # every entry keeps its name
        self.assertEqual(format_docs([]), "")

    def test_fingerprint_changes_with_corpus(self):
        self.assertNotEqual(corpus_fingerprint(DOCS), corpus_fingerprint(DOCS[:-1]))
        self.assertEqual(corpus_fingerprint(DOCS), corpus_fingerprint(list(DOCS)))


if __name__ == "__main__":
    unittest.main()
