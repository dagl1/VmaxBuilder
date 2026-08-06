from collections.abc import Generator


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def rgb_to_rgba(rgb: tuple[int, int, int] | tuple[str, str, str], alpha: float) -> str:
    """Convert RGB tuple to RGBA string."""
    if isinstance(rgb, tuple) and all(isinstance(c, str) for c in rgb):
        # If the input is a tuple of strings, convert to integers
        rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha})"


# rewrite as only rgba
COLORS_HEX = {
    "red_hex": "#FF0000",  # Standard red color
    "dark_purple_hex": "#800080",  # Dark purple for highlights
    "lightred_hex": "#FF6F21",  # A visually distinct light red color,
    "black_hex": "#000000",  # Black for trendline and boxplot
    "white_hex": "#FFFFFF",  # White for background
    "lightblue_hex": "#1F77B4",  # Light blue for scatter points
    "orange_hex": "#FFA500",  # Orange for background bars
}
COLORS_RGB = {name: hex_to_rgb(hex_color) for name, hex_color in COLORS_HEX.items()}


def custom_colorblind_color_discrete_palette() -> (
    tuple[
        list[str],  # hex
        list[str],  # rgb
        list[str],  # rgba
        list[str],  # hsl
        list[tuple[int, int, int]],  # as tuple
    ]
):
    """
    Taken from https://www.nature.com/articles/nmeth.1618
    Wong, Bang. "Points of view: Color blindness." (2011): 441-441.

    Then expanded using Github Copilot
    :return:
    """
    colors = [
        (230, 159, 0),  # Orange
        (86, 180, 233),  # Sky Blue
        (128, 0, 128),  # Purple
        (240, 228, 66),  # Yellow
        (0, 158, 115),  # Green
        (0, 114, 178),  # Blue
        (213, 94, 0),  # Red
        (190, 190, 0),  # Olive
        (204, 121, 167),  # Pink
        (128, 128, 128),  # Gray
        (0, 0, 0),
        (0, 128, 255),  # Bright Blue
        (255, 128, 0),  # Bright Orange
        (128, 0, 0),  # Maroon
        (0, 128, 0),  # Dark Green
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cyan
        (128, 128, 0),  # Olive Green
    ]

    # convert to hex
    colors_hex = ["#{:02x}{:02x}{:02x}".format(*color) for color in colors]
    # convert to rgb
    colors_rgb = ["rgb({},{},{})".format(*color) for color in colors]
    # convert to rgba
    colors_rgba = ["rgba({},{},{},1)".format(*color) for color in colors]
    # convert to hsl
    colors_hsl = ["hsl({},{},{})".format(*color) for color in colors]

    return (colors_hex, colors_rgb, colors_rgba, colors_hsl, colors)


def yield_discrete_colorblind_color(
    colors: list[tuple[str, str, str]] | list[tuple[int, int, int]],
    start: int,
) -> Generator[tuple[str, str, str] | tuple[int, int, int], None, None]:
    """
    Yield a discrete colorblind-friendly color from the palette.

    Args:
        colors (list[tuple[str, str, str]]): List of colors in RGB format.
        start (int): Starting index for yielding colors.

    Yields:
        tuple[int, int, int]: RGB color tuple.
    """
    for i in range(start, len(colors)):
        yield colors[i]
