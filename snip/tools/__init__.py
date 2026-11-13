"""Editor tools, one small module each."""
from .selector import SelectTool
from .pen import PenTool
from .highlighter import HighlighterTool
from .arrow import ArrowTool
from .rect import RectTool
from .text import TextTool
from .crop import CropTool

# (key, label, class) in toolbar order
TOOLS = [
    ("select", "Select", SelectTool),
    ("pen", "Pen", PenTool),
    ("highlighter", "Highlighter", HighlighterTool),
    ("arrow", "Arrow", ArrowTool),
    ("rect", "Rectangle", RectTool),
    ("text", "Text", TextTool),
    ("crop", "Crop", CropTool),
]
