from collections.abc import Generator, Sequence


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


def blend_hex_color(hex_color_one: str, hex_color_two: str, factor: float = 0.5) -> str:
    """Generated: validation needed.

    Description:
        Blend two hex colours using linear interpolation.

    Args:
        hex_color_one (str): First hex colour.
        hex_color_two (str): Second hex colour.
        factor (float): Interpolation factor where ``1.0`` keeps first colour and
            ``0.0`` keeps second colour.

    Returns:
        str: Blended hex colour.

    Raises:
        ValueError: If ``factor`` is outside inclusive ``[0.0, 1.0]`` range.
    """
    if factor < 0.0 or factor > 1.0:
        raise ValueError("factor must be between 0.0 and 1.0")

    red_one, green_one, blue_one = hex_to_rgb(hex_color_one)
    red_two, green_two, blue_two = hex_to_rgb(hex_color_two)

    blended_red = int(red_one * factor + red_two * (1.0 - factor))
    blended_green = int(green_one * factor + green_two * (1.0 - factor))
    blended_blue = int(blue_one * factor + blue_two * (1.0 - factor))
    return rgb_to_hex((blended_red, blended_green, blended_blue))


def blend_hex_color_sequence(hex_colors: Sequence[str]) -> str:
    """Generated: validation needed.

    Description:
        Blend ordered sequence of hex colours into one representative colour.

    Args:
        hex_colors (Sequence[str]): Ordered colour sequence to blend.

    Returns:
        str: Blended hex colour.

    Raises:
        ValueError: If ``hex_colors`` is empty.
    """
    if not hex_colors:
        raise ValueError("hex_colors must contain at least one colour")
    if len(hex_colors) == 1:
        return hex_colors[0]

    amount_of_steps = len(hex_colors)
    factor_steps = 1 / (amount_of_steps - 1)

    blended_color = hex_colors[0]
    for index, hex_color in enumerate(hex_colors[1:], start=1):
        blended_color = blend_hex_color(
            blended_color,
            hex_color,
            factor=index * factor_steps,
        )
    return blended_color


# rewrite as only rgba
COLORS_HEX = {
    "gray_hex": "#808080",  # Standard gray color
    "gray_red_hex": "#D0A9A9",  # Dark gray for trendline and boxplot
    "red_hex": "#FF0000",  # Standard red color
    "dark_purple_hex": "#800080",  # Dark purple for highlights
    "lightred_hex": "#FF6F21",  # A visually distinct light red color,
    "black_hex": "#000000",  # Black for trendline and boxplot
    "white_hex": "#FFFFFF",  # White for background
    "lightblue_hex": "#1F77B4",  # Light blue for scatter points
    "orange_hex": "#FFA500",  # Orange for background bars
}
COLORS_RGB = {name: hex_to_rgb(hex_color) for name, hex_color in COLORS_HEX.items()}


def custom_colorblind_color_discrete_palette() -> tuple[
    list[str],  # hex
    list[str],  # rgb
    list[str],  # rgba
    list[str],  # hsl
    list[tuple[int, int, int]],  # as tuple
]:
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
