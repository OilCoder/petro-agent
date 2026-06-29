"""Unsupervised electrofacies via a deterministic numpy k-means (no sklearn).

Clusters depth samples on standardized log curves into k electrofacies. No core labels, so
this is descriptive, not predictive — the report states it. Deterministic given a pinned seed
(Charter: seeds pinned). The agent selects the method; the engine computes the labels.
"""

import numpy as np

VERSION = "0.1.0"


def kmeans_labels(x: np.ndarray, k: int = 4, iters: int = 50, seed: int = 42) -> np.ndarray:
    """Cluster rows of ``x`` into ``k`` groups (Lloyd's algorithm, fixed seed).

    Args:
        x: (n, m) standardized feature matrix, no NaN rows.
        k: number of clusters.
        iters: max iterations (stops early on convergence).
        seed: pinned RNG seed for reproducible centroid initialization.

    Returns:
        (n,) integer cluster labels in ``[0, k)``.
    """
    rng = np.random.default_rng(seed)
    n = x.shape[0]
    k = min(k, n)
    cent = x[rng.choice(n, size=k, replace=False)].copy()
    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        dist = ((x[:, None, :] - cent[None, :, :]) ** 2).sum(axis=2)
        new = dist.argmin(axis=1)
        if np.array_equal(new, labels):
            break
        labels = new
        for j in range(k):
            members = x[labels == j]
            if members.size:
                cent[j] = members.mean(axis=0)
    return labels


def electrofacies_summary(features: np.ndarray, n_facies: int = 4, seed: int = 42) -> dict:
    """Cluster standardized features and summarize the electrofacies.

    Args:
        features: (n, m) raw feature matrix (curves as columns); rows with any NaN are dropped.
        n_facies: target number of electrofacies.
        seed: pinned RNG seed.

    Returns:
        ``{n_facies, n_samples, sizes}`` where ``sizes`` maps facies id -> sample count.
    """
    x = np.asarray(features, dtype=float)
    finite = x[~np.isnan(x).any(axis=1)]
    if finite.shape[0] < n_facies:
        return {"n_facies": 0, "n_samples": int(finite.shape[0]), "sizes": {}}
    mu = finite.mean(axis=0)
    sd = finite.std(axis=0)
    sd[sd == 0] = 1.0
    labels = kmeans_labels((finite - mu) / sd, k=n_facies, seed=seed)
    sizes = {str(j): int(np.count_nonzero(labels == j)) for j in range(n_facies)}
    return {"n_facies": n_facies, "n_samples": int(finite.shape[0]), "sizes": sizes}
