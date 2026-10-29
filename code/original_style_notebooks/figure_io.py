"""Transparent Matplotlib PNG+SVG export for the original plot notebooks.
Keep the original plots' style, geometry and save names; add an SVG sibling.
"""
from pathlib import Path

def enforce_arial_sans(fig):
    """Use one font family for every text artist without changing size or weight.

    Arial is used when installed (e.g. Windows). DejaVu Sans/Helvetica are fallbacks.
    This corrects legacy notebook cells which reset rcParams to serif and also
    handles mathematical annotations and figure-level labels consistently.
    """
    from matplotlib import rcParams
    from matplotlib.text import Text
    rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'DejaVu Sans', 'Helvetica'],
        'mathtext.fontset': 'dejavusans',
        'svg.fonttype': 'none',
    })
    for artist in fig.findobj(match=Text):
        artist.set_fontfamily('sans-serif')

def activate_svg_autosave():
    from matplotlib.figure import Figure
    if getattr(Figure.savefig,'_svg_enabled',False):
        return
    original = Figure.savefig
    def savefig_png_and_svg(self, fname, *args, **kwargs):
        enforce_arial_sans(self)
        result = original(self, fname, *args, **kwargs)
        if isinstance(fname,(str,Path)) and str(fname).lower().endswith('.png'):
            svg_kwargs = dict(kwargs)
            svg_kwargs.pop('dpi',None)
            original(self, str(Path(fname).with_suffix('.svg')), *args, **svg_kwargs)
        return result
    savefig_png_and_svg._svg_enabled=True
    Figure.savefig=savefig_png_and_svg
