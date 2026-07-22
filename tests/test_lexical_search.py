import gc
import hashlib
import tempfile
import unittest
from pathlib import Path

from backend import server
from backend.lexical_compare import curated_comparison_catalog, parse_comparison_terms


class LexicalSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        server.DB_PATH = Path(cls.temp_dir.name) / "test.sqlite"
        server.init_db()

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        cls.temp_dir.cleanup()

    def first_label(self, query):
        first = server.lexical_search(query)["results"][0]
        return first.get("headword") or first.get("form")

    def test_exact_headword_and_word_form(self):
        self.assertEqual(self.first_label("inspect"), "inspect")
        self.assertEqual(self.first_label("inspection"), "inspection")
        self.assertEqual(self.first_label("inspected"), "inspect")

    def test_chinese_root_and_etymon_queries(self):
        self.assertIn(self.first_label("观察"), {"inspect", "spect"})
        self.assertEqual(self.first_label("spect"), "spect")
        self.assertEqual(self.first_label("specere"), "spect")

    def test_affix_queries(self):
        self.assertEqual(self.first_label("re-"), "re-")
        self.assertEqual(self.first_label("-tion"), "-tion")

    def test_empty_query_returns_browsable_catalog(self):
        payload = server.lexical_search("")
        self.assertGreaterEqual(payload["count"], 10)
        self.assertTrue(any(item["type"] == "entry" for item in payload["results"]))
        self.assertTrue(any(item["type"] == "morpheme" for item in payload["results"]))

    def test_collocations_include_bilingual_relations(self):
        entry = server.lexical_search("inspect")["results"][0]
        collocation = entry["collocations"][0]
        self.assertEqual(collocation["phrase"], "inspect the premises")
        self.assertEqual(collocation["meaning_zh"], "检查场所")
        self.assertTrue(collocation["synonyms"][0]["meaning_zh"])
        self.assertTrue(collocation["antonyms"][0]["meaning_zh"])

    def test_examples_include_chinese_translations(self):
        entry = server.lexical_search("inspected")["results"][0]
        self.assertEqual(entry["headword"], "inspect")
        self.assertIn("inspected", entry["examples"][1]["text"].lower())
        self.assertEqual(entry["examples"][1]["translation"], "这些文件在批准之前必须经过审查。")

    def test_phrase_relations_are_searchable(self):
        results = server.lexical_search("check for damage")["results"]
        self.assertEqual(results[0]["type"], "query")
        self.assertEqual(results[0]["kind"], "phrase")
        self.assertEqual(results[0]["translation_zh"], "查看有无损坏")
        self.assertTrue(any(item.get("headword") == "inspect" for item in results))

    def test_unknown_term_keeps_translation_learning_state_and_context(self):
        term = "meaningful control"
        now = server.utc_now()
        digest = hashlib.sha256(term.encode("utf-8")).hexdigest()
        with server.db() as conn:
            article = conn.execute("SELECT id FROM articles WHERE source = 'seed'").fetchone()
            conn.execute(
                """INSERT INTO cards (term, kind, context, source_article_id, status, created_at, updated_at)
                   VALUES (?, 'phrase', ?, ?, 'new', ?, ?)""",
                (term, "People need meaningful control over their data.", article["id"], now, now),
            )
            conn.execute(
                """INSERT INTO translation_cache
                   (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                   VALUES (?, 'EN', 'ZH-HANS', 'deepl', ?, ?, ?)""",
                (digest, term, "真正的掌控权", now),
            )
        item = server.lexical_search(term)["results"][0]
        self.assertEqual(item["type"], "query")
        self.assertTrue(item["saved"])
        self.assertEqual(item["translation_zh"], "真正的掌控权")
        self.assertTrue(item["contexts"])

    def test_unknown_single_word_returns_actionable_query(self):
        item = server.lexical_search("ubiquitous")["results"][0]
        self.assertEqual(item["type"], "query")
        self.assertEqual(item["term"], "ubiquitous")
        self.assertEqual(item["kind"], "word")

    def test_personal_contexts_keep_multiple_examples_and_cached_chinese(self):
        sentence_one = "Readers respect evidence when evaluating a difficult claim."
        sentence_two = "Writers respect evidence by separating facts from opinion."
        now = server.utc_now()
        with server.db() as conn:
            conn.execute(
                """INSERT INTO articles
                   (title, language, level, topic, source, body, created_at, updated_at)
                   VALUES (?, 'English', 'B2', 'Research', 'test', ?, ?, ?)""",
                ("Respecting evidence", f"{sentence_one} {sentence_two}", now, now),
            )
            for source, translated in ((sentence_one, "读者在评估困难论点时尊重证据。"), (sentence_two, "作者通过区分事实与观点来尊重证据。")):
                conn.execute(
                    """INSERT INTO translation_cache
                       (text_hash, source_lang, target_lang, provider, source_text, translated_text, created_at)
                       VALUES (?, 'EN', 'ZH-HANS', 'test', ?, ?, ?)""",
                    (hashlib.sha256(source.encode("utf-8")).hexdigest(), source, translated, now),
                )
        context = server.lexical_query_context("respect")
        matched = [item for item in context["contexts"] if item["text"] in {sentence_one, sentence_two}]
        self.assertEqual(len(matched), 2)
        self.assertTrue(all(item["translation_zh"] for item in matched))

    def test_contextual_collocations_are_ranked_by_observed_count(self):
        contexts = [
            {"text": "Teams inspect for damage."},
            {"text": "Engineers inspect for damage."},
            {"text": "Managers closely inspect reports."},
        ]
        collocations = server.contextual_collocations("inspect", contexts)
        self.assertEqual(collocations[0]["phrase"].lower(), "inspect for damage")
        self.assertEqual(collocations[0]["observed_count"], 2)
        self.assertEqual(collocations[0]["source"], "个人文章语料")

    def test_verified_morphology_resolution_enriches_wordnet_results(self):
        payload = server.lexical_search("inspecting")
        self.assertEqual(payload["resolution"], {"from": "inspecting", "to": "inspect"})
        self.assertTrue(any(item.get("headword") == "inspect" for item in payload["results"]))

    def test_spelling_suggestions_only_return_indexed_terms(self):
        payload = server.lexical_search("inspeckt")
        self.assertIn("inspect", payload["suggestions"])
        with server.db() as conn:
            self.assertTrue(conn.execute(
                "SELECT 1 FROM wordnet_lemmas WHERE normalized = ? LIMIT 1", (payload["suggestions"][0],)
            ).fetchone() or any(
                row["headword"].casefold() == payload["suggestions"][0]
                for row in conn.execute("SELECT headword FROM dictionary_entries")
            ))

    def test_full_query_history_is_persistent_and_quick_search_is_not_tracked(self):
        with server.db() as conn:
            conn.execute("DELETE FROM lexical_queries")
        server.lexical_search("inspect")
        self.assertEqual(server.lexical_query_history()["recent"], [])
        server.lexical_search("Inspect", track=True)
        server.lexical_search("inspect", track=True)
        history = server.lexical_query_history()
        self.assertEqual(history["recent"][0]["normalized"], "inspect")
        self.assertEqual(history["recent"][0]["lookup_count"], 2)
        self.assertEqual(history["recent"][0]["query_kind"], "word")

    def test_multiword_comparison_accepts_common_separators_and_preserves_order(self):
        self.assertEqual(parse_comparison_terms("cordial, keen, zeal"), ["cordial", "keen", "zeal"])
        self.assertEqual(parse_comparison_terms("zeal / cordial / keen"), ["zeal", "cordial", "keen"])
        self.assertEqual(parse_comparison_terms("cordial vs. keen"), ["cordial", "keen"])
        with self.assertRaisesRegex(ValueError, "two to five different terms"):
            parse_comparison_terms("keen, keen")

    def test_curated_comparison_explains_boundaries_instead_of_merging_chinese_meanings(self):
        payload = server.lexical_comparison("cordial, keen, zeal")
        self.assertTrue(payload["reviewed"])
        self.assertEqual(payload["mode"], "curated")
        self.assertEqual([item["pos"] for item in payload["items"]], ["adjective", "adjective", "noun"])
        self.assertIn("人际态度", payload["dimensions"][0]["value"])
        self.assertEqual(payload["items"][0]["patterns"][0], "a cordial welcome")
        self.assertIn("待人 cordial", payload["memory_rule"])

    def test_common_curated_groups_are_complete_and_queryable_in_any_order(self):
        from backend.lexical_compare import CURATED_COMPARISONS

        self.assertEqual(len(CURATED_COMPARISONS), 45)
        self.assertEqual(sum(len(group["terms"]) for group in CURATED_COMPARISONS), 117)
        for group in CURATED_COMPARISONS:
            query = ", ".join(reversed(group["terms"]))
            payload = server.lexical_comparison(query)
            self.assertTrue(payload["reviewed"], group["slug"])
            self.assertEqual(
                [item["term"] for item in payload["items"]],
                list(reversed(group["terms"])),
            )
            self.assertTrue(payload["memory_rule"])
            self.assertGreaterEqual(len(payload["dimensions"]), 3)
            for item in payload["items"]:
                self.assertTrue(item["focus_en"])
                self.assertGreaterEqual(len(item["patterns"]), 2)
                self.assertTrue(item["avoid"])
                self.assertTrue(item["example_zh"])
                self.assertEqual(item["sources"], ["本地人工整理基础组"])
                self.assertIn("evidence_sources", item)

    def test_composition_group_preserves_whole_part_direction(self):
        payload = server.lexical_comparison("comprise, compose, constitute, consist of")
        self.assertTrue(payload["reviewed"])
        self.assertEqual([item["term"] for item in payload["items"]], [
            "comprise", "compose", "constitute", "consist of",
        ])
        self.assertIn("整体 comprises", payload["memory_rule"])
        self.assertIn("不用被动", payload["items"][3]["avoid"])

    def test_curated_catalog_exposes_every_group_without_editorial_body_duplication(self):
        catalog = curated_comparison_catalog()
        self.assertEqual(len(catalog), 105)
        self.assertEqual(catalog[0]["query"], "cordial, keen, zeal")
        composition = next(item for item in catalog if item["slug"] == "compose-comprise-constitute-consist-of")
        self.assertEqual(composition["terms"], ["compose", "comprise", "constitute", "consist of"])
        self.assertNotIn("items", composition)
        self.assertEqual(sum(group["reviewed"] for group in catalog), 45)
        self.assertEqual(sum(group["catalog_status"] == "candidate" for group in catalog), 60)

    def test_lookalike_groups_expose_spelling_grammar_and_category(self):
        payload = server.lexical_comparison("complement, compliment")
        self.assertTrue(payload["reviewed"])
        self.assertEqual(payload["confusion_type"], "lookalike")
        self.assertEqual(payload["dimensions"][0]["label"], "拼写锚点")
        self.assertIn("词性", payload["dimensions"][1]["label"])
        self.assertEqual(payload["items"][0]["pos"], "noun/verb")
        self.assertIn("补充", payload["items"][0]["meaning_zh"])

    def test_lookalike_catalog_has_high_frequency_homophone_and_direction_groups(self):
        catalog = curated_comparison_catalog()
        lookalikes = [group for group in catalog if group["confusion_type"] == "lookalike"]
        self.assertEqual(len(lookalikes), 44)
        self.assertTrue(any(group["slug"] == "cite-site-sight" for group in lookalikes))
        self.assertTrue(any(group["slug"] == "emigrate-immigrate" for group in lookalikes))

    def test_candidate_group_exposes_evidence_without_claiming_review(self):
        payload = server.lexical_comparison("accurate, precise, exact")
        self.assertFalse(payload["reviewed"])
        self.assertEqual(payload["mode"], "candidate")
        self.assertEqual(payload["catalog_status"], "candidate")
        self.assertIn("等待", payload["summary"])
        self.assertTrue(all(not item["patterns"] for item in payload["items"]))

    def test_frontend_comparison_catalog_can_filter_lookalikes(self):
        source = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
        markup = (Path(__file__).parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
        self.assertIn('group.confusion_type === state.lexicalComparisonFilter', source)
        self.assertIn('data-comparison-filter="lookalike"', markup)

    def test_single_word_search_links_to_its_common_confusion_group(self):
        profile = server.lexical_search("efficient")["results"][0]["learning_profile"]
        self.assertEqual(profile["meaning_zh"], "高效的；效率高的")
        self.assertEqual(profile["related_terms"], ["effective"])
        self.assertIn("little wasted time", profile["focus_en"])

    def test_single_word_search_promotes_the_curated_learning_sense_without_deleting_polysemy(self):
        item = server.lexical_search("cordial")["results"][0]
        profile = item["learning_profile"]
        self.assertEqual(profile["pos"], "adjective")
        self.assertEqual(profile["meaning_zh"], "热情友好的；诚恳而有礼的")
        self.assertIn("warm and friendly", profile["focus_en"])
        self.assertEqual(profile["patterns"][0], "a cordial welcome")
        self.assertEqual(profile["related_terms"], ["keen", "zeal"])

    def test_unreviewed_comparison_uses_evidence_without_promoting_open_phrases(self):
        payload = server.lexical_comparison("happy, glad")
        self.assertFalse(payload["reviewed"])
        self.assertEqual(payload["mode"], "evidence")
        self.assertEqual([item["term"] for item in payload["items"]], ["happy", "glad"])
        self.assertTrue(all(not item["patterns"] for item in payload["items"]))
        self.assertIn("不作强行结论", payload["source_note"])

    def test_frontend_dictionary_contract_keeps_bilingual_senses_and_two_voices(self):
        source = (Path(__file__).parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
        self.assertIn('function pronunciationControls(', source)
        self.assertIn('data-voice="en-GB"', source)
        self.assertIn('data-voice="en-US"', source)
        self.assertIn('function wordnetNeedsChinese(', source)
        self.assertIn('sense.definition_translations?.[definitionIndex]', source)
        self.assertIn('sense.example_translations?.[exampleIndex]', source)
        self.assertIn('补充真实语境（未按义项归类）', source)


if __name__ == "__main__":
    unittest.main()
