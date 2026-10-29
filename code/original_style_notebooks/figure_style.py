"""Publication figure defaults. Uses Arial on Windows and standard sans-serif fallbacks elsewhere."""
from matplotlib import rcParams, font_manager
from pathlib import Path
import warnings

ICEV = '#d62728'
BEV = '#ffcc00'
PHEV = '#1f77b4'
NEUTRAL = '#447C78'  # Restrained teal for model estimates; vehicle colors remain reserved
NEUTRAL_LIGHT = '#B3CECA'  # Muted teal confidence interval
SECONDARY = '#B08E5E'  # Muted sand for secondary metrics / marginal proxies
TEAL = '#447C78'  # Restrained teal used consistently for a one-series diagnostic

LABELS = {
    'V2G':'V2G',
    'Battery Charging':'Battery-charging',
    'EV Subsidy':'EV Subsidy',
    'Tax Incentive':'Tax incentive',
    'CAFC Credit':'CAFC credit',
    'NEV Credit':'NEV credit',
    'Grid Decarb':'Grid decarbonization',
    'Charging Station':'Charging station deployment',
}

def style():
    names = {f.name for f in font_manager.fontManager.ttflist}
    if 'Arial' not in names:
        warnings.warn('Arial unavailable in this preview environment; DejaVu Sans will be used. Windows uses Arial.')
    rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'DejaVu Sans', 'Helvetica'],
        'mathtext.fontset': 'dejavusans',
        'font.size': 9,
        'axes.titlesize': 10,
        'axes.labelsize': 9,
        'xtick.labelsize': 8,
        'ytick.labelsize': 8,
        'legend.fontsize': 8,
        'figure.titlesize': 12,
        'axes.unicode_minus': False,
        'savefig.dpi': 300,
        'svg.fonttype': 'none',
        'pdf.fonttype': 42,
        'axes.spines.top': True,
        'axes.spines.right': True,
    })

def save(fig, root, stem):
    from figure_io import enforce_arial_sans
    enforce_arial_sans(fig)
    folder=Path(root);folder.mkdir(parents=True,exist_ok=True)
    fig.savefig(folder/(stem+'.png'), dpi=300, bbox_inches='tight',pad_inches=0.10)
    fig.savefig(folder/(stem+'.svg'), bbox_inches='tight',pad_inches=0.10)
