if __name__ == "__main__":
    import os
    import sys

    # we create a data set with 300 samples, where we have 3 hidden variables
    # male vs female
    # disease vs healthy
    # young vs old
    #
    # we have 20 features, 14 randomly distributed ones
    # then we have 6 features that are correlated with the hidden variables
    #
    # Generate synthetic data
    import numpy as np
    import pandas as pd
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    # Reproducibility
    np.random.seed(42)

    # Number of samples
    n = 300

    # ============================================================
    # 1. Generate the 3 hidden variables
    # ============================================================

    # 0 = female, 1 = male
    sex = np.random.binomial(1, 0.5, n)

    # 0 = healthy, 1 = disease
    disease = np.random.binomial(1, 0.5, n)

    # 0 = young, 1 = old
    age = np.random.binomial(1, 0.5, n)

    # ============================================================
    # 2. Generate 20 observed features
    # ============================================================

    # Start with 14 completely random features
    X = np.random.normal(0, 1, size=(n, 20))

    # ============================================================
    # 3. Create 6 features correlated with hidden variables
    # ============================================================

    # Features 1-2: correlated with SEX
    X[:, 14] = 2 * sex + np.random.normal(0, 1, n)
    X[:, 15] = -1.5 * sex + np.random.normal(0, 1, n)

    # Features 3-4: correlated with DISEASE
    X[:, 16] = 2 * disease + np.random.normal(0, 1, n)
    X[:, 17] = -1.5 * disease + np.random.normal(0, 1, n)

    # Features 5-6: correlated with AGE
    X[:, 18] = 2 * age + np.random.normal(0, 1, n)
    X[:, 19] = -1.5 * age + np.random.normal(0, 1, n)

    # ============================================================
    # 4. Put everything into a DataFrame
    # ============================================================

    feature_names = [f"feature_{i + 1}" for i in range(20)]

    df = pd.DataFrame(X, columns=feature_names)

    # Add hidden variables
    df["sex"] = sex
    df["disease"] = disease
    df["age"] = age

    # now pca fit, and show pc 1 and 2 on plot, show eigen value, and a variance explaiend
    #
    # Data analysis isn't available right now. Do you want to continue without it
    import matplotlib.pyplot as plt

    # Fit PCA
    pca = PCA(n_components=20)
    X_pca = pca.fit_transform(X)
    # show the first 5 samples feature 13 14 15
    print("First 5 samples of the original features:\n", X[13:18, 13:16])

    # Print values
    print("Eigenvalues (Variance):", pca.explained_variance_)
    print("Explained Variance Ratio:", pca.explained_variance_ratio_)

    plt.figure(figsize=(16, 6))
    plt.subplot(1, 2, 1)
    plt.scatter(X_pca[:, 0], X_pca[:, 1], c=disease, cmap="coolwarm", alpha=0.7)
    plt.title("PCA: Principal Component 1 vs 2 (Original Features)")
    plt.xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.2f}%)")
    plt.ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.2f}%)")
    plt.colorbar(label="Disease Status")
    plt.grid(True)
    # now we duplicate a single sex_related feature 20 times and add to tdata

    # X[:, 14]
    X_new = np.hstack([X, np.tile(X[:, 14].reshape(-1, 1), (1, 20))])
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    # show the first 5 samples feature 13 14 15 and 21 22 23

    # Fit PCA
    new_pca = PCA(n_components=20)
    new_X_pca = new_pca.fit_transform(X_new)
    proof_cols = {
        "Feature_14 (Random)": X_new[:5, 13],
        "Feature_15 (Sex-linked)": X_new[:5, 14],
        "Duplicate_1 (Idx 20)": X_new[:5, 20],
        "Duplicate_2 (Idx 21)": X_new[:5, 21],
        "Duplicate_3 (Idx 22)": X_new[:5, 22],
    }
    proof_df = pd.DataFrame(proof_cols)
    print("First 5 samples of the original and duplicated features:\n", proof_df)

    # Print values
    print("Eigenvalues (Variance):", new_pca.explained_variance_)
    print("Explained Variance Ratio:", new_pca.explained_variance_ratio_)

    plt.subplot(1, 2, 2)
    plt.scatter(new_X_pca[:, 0], new_X_pca[:, 1], c=disease, cmap="coolwarm", alpha=0.7)
    plt.title("PCA: Principal Component 1 vs 2 (With Duplicated Feature)")
    plt.xlabel(f"PC1 ({new_pca.explained_variance_ratio_[0] * 100:.2f}%)")
    plt.ylabel(f"PC2 ({new_pca.explained_variance_ratio_[1] * 100:.2f}%)")
    plt.colorbar(label="Disease Status")
    plt.grid(True)

    plt.tight_layout()
    plt.show()
