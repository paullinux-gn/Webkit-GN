"""Matching hue families for text and highlight palettes."""
import colorsys

LIGHTNESS=(.94,.84,.70,.54,.36,.20)
HUES=(("Red",0,.72),("Orange",30,.85),("Yellow",50,.85),
      ("Green",135,.65),("Teal",180,.65),("Blue",215,.75),
      ("Purple",275,.65),("Pink",330,.72),("Brown",25,.42))
MODIFIERS=("Pastel ","Light ","Soft ","","Dark ","Deep ")
NEUTRALS=(("White","#ffffff"),("Silver","#dddddd"),("Light grey","#b3b3b3"),
          ("Grey","#888888"),("Charcoal","#5c5c5c"),("Black","#202020"))

def tint(hue,saturation,lightness):
    rgb=colorsys.hls_to_rgb(hue/360,lightness,saturation)
    return '#'+''.join(f'{round(channel*255):02x}' for channel in rgb)

families=[NEUTRALS]
for name,hue,saturation in HUES:
    families.append(tuple((prefix+name.lower() if prefix else name,tint(hue,saturation,lightness))
                          for prefix,lightness in zip(MODIFIERS,LIGHTNESS)))
COLOUR_FAMILIES=tuple(tuple(name for name,_ in family) for family in families)
TEXT_COLOURS=tuple(colour for family in families for colour in family)
HIGHLIGHT_COLOURS=TEXT_COLOURS

def palette_positions(colours):
    names={name for name,_ in colours}
    return {name:(column,row) for column,family in enumerate(COLOUR_FAMILIES)
            for row,name in enumerate(name for name in family if name in names)}
