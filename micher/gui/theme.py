"""
Micher GUI Design System — colors, fonts, constants.
Dark navy + cyan accent palette for a premium network-tool feel.
"""

# ── Color Palette ────────────────────────────────────────────────────────── #
BG_DARK        = "#0d1117"     # main background
BG_CARD        = "#161b22"     # card / panel background
BG_CARD_HOVER  = "#1c2333"     # hover state
BG_INPUT       = "#0d1117"     # input field bg
BORDER         = "#30363d"     # subtle borders
BORDER_FOCUS   = "#58a6ff"     # focused borders

ACCENT_CYAN    = "#00d4ff"     # primary accent
ACCENT_BLUE    = "#58a6ff"     # secondary accent
ACCENT_GREEN   = "#3fb950"     # success / online
ACCENT_YELLOW  = "#d29922"     # warning / hotspot
ACCENT_RED     = "#f85149"     # error / offline
ACCENT_PURPLE  = "#bc8cff"     # special

TEXT_PRIMARY   = "#e6edf3"     # main text
TEXT_SECONDARY = "#8b949e"     # muted text
TEXT_DIM       = "#484f58"     # very muted

# Per-interface-type colors (for speed bars, graphs)
IFACE_COLORS = {
    "ethernet": "#58a6ff",     # blue
    "wifi":     "#3fb950",     # green
    "hotspot":  "#d29922",     # orange/yellow
    "unknown":  "#bc8cff",     # purple
}

GRAPH_COLORS = ["#00d4ff", "#3fb950", "#d29922", "#bc8cff", "#f85149", "#58a6ff"]

# ── Typography ───────────────────────────────────────────────────────────── #
FONT_FAMILY    = "Segoe UI"    # Windows; customtkinter handles Linux fallback
FONT_SIZE_XL   = 28
FONT_SIZE_LG   = 18
FONT_SIZE_MD   = 14
FONT_SIZE_SM   = 12
FONT_SIZE_XS   = 10

# ── Spacing & Shape ─────────────────────────────────────────────────────── #
CORNER_RADIUS  = 12
PADDING_SM     = 8
PADDING_MD     = 16
PADDING_LG     = 24

# ── Window ───────────────────────────────────────────────────────────────── #
WINDOW_MIN_W   = 900
WINDOW_MIN_H   = 650
