from dataclasses import dataclass


@dataclass(slots=True)
class MValueTrimmingConfig:
    """Generated: validation needed.

    Description:
        Configuration for M-value trimming. To assess trimmability, M-value assumes that
        expression data is in linear space (not log transformed), and then checks for each
        gene across the samples if the high and low percentile values (denoted by the
        trim_percentiles config) of the gene's expression differ by more or less than the
        denoted threshold in log 2 (log2(high/low)). Note that trimmable genes are not
        automatically trimmed, only marked to be eligible for trimming during IFP allocation.

    Args:
        trim_correction_addition (float): Value added to all reactions' IFP sums during
            trimming to prevent extremely lowly expressed genes to be denoted as unstable.
        trim_percentiles (tuple[float, float]): Lower and upper percentiles used to
            determine whether gene is trimmable.
        trim_threshold (float): Threshold used to determine whether gene is trimmable:
            In particular genes whose upper and lower percentiles after addition of
            trim_correction_addition are below this threshold will be considered stable
            enough to be trimmed.
    """

    trim_enable: bool = True
    trim_correction_addition: float = 2
    trim_percentiles: tuple[float, float] = (2.5, 97.5)
    trim_threshold: float = 0.585  # is 1.5 in log2
    trim_separate_sample_groups: dict[str, list[str]] | None = None
