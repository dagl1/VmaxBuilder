import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures


def _create_trendline(
    X,
    result_df,
    y,
    trendline_type: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    if trendline_type == "linear":
        lr = LinearRegression()
        lr.fit(X, y)

        # R²
        r_squared = lr.score(X, y)

        # Slope
        slope = lr.coef_[0][0] if lr.coef_.ndim > 1 else lr.coef_[0]
        x_range = np.linspace(
            result_df["missing_count"].min(),
            result_df["missing_count"].max(),
            100,
        ).reshape(-1, 1)

        y_pred = lr.predict(x_range)
        y_fitted = lr.predict(X)

        # Make both 1D
        x_values = X.flatten()
        y_values = np.asarray(y).flatten()
        y_fitted = np.asarray(y_fitted).flatten()

        residuals = y_values - y_fitted

        # --------------------------------------------------
        # 3. Sort by X
        # --------------------------------------------------

        sorted_indices = np.argsort(x_values)

        x_sorted = x_values[sorted_indices]
        residuals_sorted = residuals[sorted_indices]

        # --------------------------------------------------
        # 4. Local 68% residual interval
        # --------------------------------------------------

        window_size = max(20, len(x_sorted) // 10)

        lower_quantiles = []
        upper_quantiles = []
        x_centers = []

        for i in range(len(x_sorted)):
            start = max(0, i - window_size // 2)
            end = min(len(x_sorted), i + window_size // 2)

            local_residuals = residuals_sorted[start:end]
            lower_quantiles.append(np.quantile(local_residuals, 0.16))
            upper_quantiles.append(np.quantile(local_residuals, 0.84))
            x_centers.append(x_sorted[i])

        lower_residual = np.interp(
            x_range.flatten(),
            x_centers,
            lower_quantiles,
        )

        upper_residual = np.interp(
            x_range.flatten(),
            x_centers,
            upper_quantiles,
        )
        y_lower = y_pred.flatten() + lower_residual
        y_upper = y_pred.flatten() + upper_residual

        # Format the legend name for linear
        trace_name = f"Linear trend (68% interval) (R²={r_squared:.2f}, Slope={slope:.3f})"
        return x_range, y_pred, y_lower, y_upper, trace_name

    elif trendline_type == "poly":
        # Fit a polynomial regression model (degree 2)
        coeffs = np.polyfit(result_df["missing_count"], result_df["stat_value"], 2)
        poly_eq = np.poly1d(coeffs)

        # Calculate R² to display in the legend/title
        missing_scalar = result_df["missing_count"].values.reshape(-1, 1)  # ty: ignore
        y_pred_poly = poly_eq(missing_scalar.flatten()).reshape(-1, 1)

        ss_res = np.sum((result_df["stat_value"] - y_pred_poly.flatten()) ** 2)
        ss_tot = np.sum((result_df["stat_value"] - np.mean(result_df["stat_value"])) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        # Generate line endpoints based on unique X values
        x_range = np.linspace(
            result_df["missing_count"].min(), result_df["missing_count"].max(), 100
        ).reshape(-1, 1)
        y_pred = poly_eq(x_range.flatten()).reshape(-1, 1)

        # prediction interval
        x = result_df["missing_count"].to_numpy()
        y = result_df["stat_value"].to_numpy()

        y_fitted = poly_eq(x)
        residuals = y - y_fitted
        sorted_indices = np.argsort(x)

        x_sorted = x[sorted_indices]
        residuals_sorted = residuals[sorted_indices]

        window_size = max(20, len(x_sorted) // 10)

        lower_quantiles = []
        upper_quantiles = []
        x_centers = []

        for i in range(len(x_sorted)):
            start = max(0, i - window_size // 2)
            end = min(len(x_sorted), i + window_size // 2)

            local_residuals = residuals_sorted[start:end]
            lower_quantiles.append(np.quantile(local_residuals, 0.16))
            upper_quantiles.append(np.quantile(local_residuals, 0.84))
            x_centers.append(x_sorted[i])

        lower_residual = np.interp(
            x_range.flatten(),
            x_centers,
            lower_quantiles,
        )

        upper_residual = np.interp(
            x_range.flatten(),
            x_centers,
            upper_quantiles,
        )
        y_lower = y_pred.flatten() + lower_residual
        y_upper = y_pred.flatten() + upper_residual

        # Format the legend name for polynomial (omitting slope)
        trace_name = f"Polynomial(2) trend (68% interval) (R²={r_squared:.2f})"
        return x_range, y_pred, y_lower, y_upper, trace_name
    else:
        raise ValueError(f"Trendline type '{trendline_type}' is not supported.")
