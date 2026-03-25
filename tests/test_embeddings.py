import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import embeddings


class EmbeddingsTests(unittest.TestCase):
    def tearDown(self) -> None:
        embeddings._load_backend.cache_clear()

    def test_sparse_backend_selected_explicitly(self):
        with patch.dict(os.environ, {"AUTOSEARCH_EMBEDDING_BACKEND": "sparse"}, clear=False):
            embeddings._load_backend.cache_clear()
            self.assertEqual(embeddings.embedding_backend_name(), "sparse-local")
            self.assertGreater(embeddings.semantic_similarity("release gate", "release gate"), 0.99)

    def test_sentence_transformer_backend_can_be_loaded_when_available(self):
        class FakeModel:
            def __init__(self, model_name):
                self.model_name = model_name

            def encode(self, text, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False):
                class _Vector:
                    def __init__(self, values):
                        self._values = values

                    def tolist(self):
                        return list(self._values)

                return _Vector([1.0, 0.0] if "release" in str(text).lower() else [0.0, 1.0])

        fake_module = type("FakeSentenceTransformersModule", (), {"SentenceTransformer": FakeModel})()
        with patch.dict(os.environ, {"AUTOSEARCH_EMBEDDING_BACKEND": "sentence_transformers", "AUTOSEARCH_EMBEDDING_MODEL": "fake-model"}, clear=False), \
             patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            embeddings._load_backend.cache_clear()
            self.assertEqual(embeddings.embedding_backend_name(), "sentence-transformers:fake-model")
            self.assertGreater(embeddings.semantic_similarity("release gate", "release gate"), 0.99)
            self.assertLess(embeddings.semantic_similarity("release gate", "gardening tips"), 0.1)


if __name__ == "__main__":
    unittest.main()
