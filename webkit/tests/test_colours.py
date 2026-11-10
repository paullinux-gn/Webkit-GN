import colorsys
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from colours import TEXT_COLOURS,HIGHLIGHT_COLOURS,COLOUR_FAMILIES,palette_positions

class ColourTests(unittest.TestCase):
    def test_matching_complete_palettes(self):
        self.assertEqual(TEXT_COLOURS,HIGHLIGHT_COLOURS)
        self.assertEqual(len(TEXT_COLOURS),60)
        self.assertEqual(len(set(value for _,value in TEXT_COLOURS)),60)
        positions=palette_positions(TEXT_COLOURS)
        self.assertEqual(len(set(positions.values())),60)
        self.assertTrue(all(len(family)==6 for family in COLOUR_FAMILIES))

    def test_each_family_has_constant_hue_and_descending_brightness(self):
        colours=dict(TEXT_COLOURS)
        for column,family in enumerate(COLOUR_FAMILIES):
            hls=[];brightness=[]
            for name in family:
                value=colours[name];rgb=tuple(int(value[i:i+2],16)/255 for i in (1,3,5))
                hls.append(colorsys.rgb_to_hls(*rgb))
                linear=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb]
                brightness.append(sum(c*w for c,w in zip(linear,(.2126,.7152,.0722))))
            self.assertTrue(all(a>b for a,b in zip(brightness,brightness[1:])),family)
            if column:
                # Allow rounding to 8-bit RGB, including very pale shades.
                hues=[item[0] for item in hls]
                self.assertLess(max(hues)-min(hues),.015,family)
                self.assertLess(max(item[2] for item in hls)-min(item[2] for item in hls),.04,family)
