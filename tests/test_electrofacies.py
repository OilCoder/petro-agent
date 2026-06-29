"""Golden tests for the deterministic numpy electrofacies (k-means)."""

import numpy as np

from src.petrophysics.electrofacies import electrofacies_summary, kmeans_labels


def test_kmeans_separates_two_blobs():
    blob_a = np.zeros((20, 2))
    blob_b = np.full((20, 2), 10.0)
    x = np.vstack([blob_a, blob_b])
    labels = kmeans_labels(x, k=2, seed=42)
    # the two blobs land in different clusters
    assert labels[0] != labels[-1]
    assert len(set(labels[:20])) == 1 and len(set(labels[20:])) == 1


def test_kmeans_deterministic():
    x = np.vstack([np.zeros((10, 2)), np.full((10, 2), 5.0)])
    assert np.array_equal(kmeans_labels(x, k=2, seed=7), kmeans_labels(x, k=2, seed=7))


def test_electrofacies_summary_counts():
    feats = np.vstack([np.zeros((20, 3)), np.full((20, 3), 8.0)])
    out = electrofacies_summary(feats, n_facies=2, seed=42)
    assert out["n_facies"] == 2 and out["n_samples"] == 40
    assert sum(out["sizes"].values()) == 40


def test_electrofacies_too_few_samples():
    out = electrofacies_summary(np.zeros((2, 3)), n_facies=4)
    assert out["n_facies"] == 0
