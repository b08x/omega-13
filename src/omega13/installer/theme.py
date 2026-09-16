"""Syncopated dark color palette mapped to Rich styles.

Source: b08x.github.io design system tokens/colors.css (.dark block).
Warm, lamp-lit night field note — never a cold IDE black.
"""

from rich.theme import Theme

# Direct hex values from the syncopated dark palette
COLORS = {
    # Surfaces
    "background":  "#211C17",
    "surface":     "#2A241D",
    "surface_2":   "#342D24",
    "bg_code":     "#1B1712",
    "popover":     "#2E2820",

    # Ink
    "foreground":  "#ECE3D2",
    "text_2":      "#C7BBA6",
    "muted":       "#968A78",
    "dim":         "#5E5546",

    # Accents
    "accent":      "#C97A5E",   # terracotta
    "accent_hi":   "#DB8E72",   # lifted terracotta
    "accent_soft": "#3A2A22",   # tinted wash
    "cyan":        "#84A4C0",   # dusty blue
    "cyan_hi":     "#9DB8CE",   # lifted blue

    # Borders
    "border":      "#3A3228",
    "border_2":    "#4B4135",

    # Status
    "success":     "#97AC78",   # olive
    "warning":     "#DB8A5C",   # burnt orange
    "danger":      "#D2715F",   # brick red
    "info":        "#84A4C0",   # dusty blue
    "question":    "#D2A653",   # ochre
    "special":     "#B488A0",   # muted plum

    # Chart (for progress bars and multi-step)
    "chart_1":     "#84A4C0",
    "chart_2":     "#D2A653",
    "chart_3":     "#97AC78",
    "chart_4":     "#B488A0",
    "chart_5":     "#D2715F",
}

SYNCOPATED_THEME = Theme({
    # Core text
    "default":         f"{COLORS['foreground']}",
    "dim":             f"{COLORS['muted']}",
    "muted":           f"{COLORS['dim']}",
    "secondary":       f"{COLORS['text_2']}",

    # Brand accents
    "accent":          f"bold {COLORS['accent']}",
    "accent.hi":       f"bold {COLORS['accent_hi']}",
    "link":            f"{COLORS['cyan']}",
    "link.hi":         f"underline {COLORS['cyan_hi']}",

    # Status
    "success":         f"{COLORS['success']}",
    "warning":         f"{COLORS['warning']}",
    "danger":          f"bold {COLORS['danger']}",
    "info":            f"{COLORS['info']}",
    "question":        f"{COLORS['question']}",
    "special":         f"{COLORS['special']}",

    # Installer step rendering
    "step.number":     f"bold {COLORS['accent']}",
    "step.title":      f"bold {COLORS['foreground']}",
    "step.done":       f"{COLORS['success']}",
    "step.skip":       f"{COLORS['text_2']}",
    "step.fail":       f"bold {COLORS['danger']}",
    "step.active":     f"bold {COLORS['accent_hi']}",

    # Components
    "banner":          f"bold {COLORS['accent_hi']}",
    "banner.border":   f"{COLORS['accent']}",
    "panel.border":    f"{COLORS['border_2']}",
    "path":            f"{COLORS['cyan']}",
    "cmd":             f"{COLORS['text_2']} on {COLORS['bg_code']}",
    "version":         f"{COLORS['special']}",

    # Progress
    "progress.bar.complete":  f"{COLORS['accent']}",
    "progress.bar.finished":  f"{COLORS['success']}",
    "progress.elapsed":       f"{COLORS['muted']}",
    "progress.percentage":    f"{COLORS['text_2']}",

    # Table
    "table.header":    f"bold {COLORS['accent']}",
    "table.border":    f"{COLORS['border']}",
})
