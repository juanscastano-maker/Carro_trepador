#!/usr/bin/env python3
"""
Dibuja la página "1. Alimentación" del diagrama de conexiones.

Genera, desde las mismas coordenadas:
  - la página 1 de docs/electronica/diagrama_conexiones.drawio (la página 2 no se toca)
  - docs/electronica/diagrama_conexiones_alimentacion.png

Uso: python3 scripts/diagrama_alimentacion.py
Para cambiar el diagrama: editar las listas CAJAS, PUERTOS, CABLES y TEXTOS y volver a correrlo.
Requiere Pillow (python3-pil).
"""

import html
import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAWIO = os.path.join(RAIZ, 'docs', 'electronica', 'diagrama_conexiones.drawio')
PNG = os.path.join(RAIZ, 'docs', 'electronica', 'diagrama_conexiones_alimentacion.png')
ANCHO, ALTO, ESCALA = 2200, 1170, 1.6

ROJO, NEGRO, NARANJA, MORADO = '#D32F2F', '#212121', '#EF6C00', '#8E24AA'
AMARILLO, CAFE, VERDE, GRIS = '#F9A825', '#6D4C41', '#2E7D32', '#9E9E9E'

# Cajas: (id, título, x, y, ancho, alto, relleno, espacio sobre el título)
CAJAS = [
    ('bat', 'Batería LiPo HV 4S<br>1100 mAh (XT30)', 40, 250, 190, 170, '#FFF3E0', 6),
    ('xt30', 'XT30 (interruptor)', 290, 300, 150, 70, '#FFFFFF', 6),
    ('fus', 'Fusible 40 A', 480, 300, 130, 70, '#FFFFFF', 6),
    ('shunt', 'Shunt 1 mΩ (≥2 W)', 650, 300, 160, 70, '#FFFFFF', 6),
    ('ina_mod', 'INA226 (módulo)', 640, 450, 180, 160, '#E8F5E9', 6),
    ('esc_d', 'ESC Skywalker V2 30A<br>delantero', 900, 290, 190, 290, '#F3E5F5', 34),
    ('esc_t', 'ESC Skywalker V2 30A<br>trasero', 1120, 290, 190, 290, '#F3E5F5', 34),
    ('bldc_d', 'BLDC XING2 1404<br>4600KV delantero', 900, 880, 190, 70, '#FFFFFF', 6),
    ('bldc_t', 'BLDC XING2 1404<br>4600KV trasero', 1120, 880, 190, 70, '#FFFFFF', 6),
    ('gy', '2 × GY-521', 900, 965, 190, 75, '#E8F5E9', 6),
    ('ina', 'INA226', 1120, 965, 190, 75, '#E8F5E9', 6),
    ('esp', 'ESP32-S3 (Freenove)', 1360, 890, 220, 150, '#E3F2FD', 6),
    ('drv', 'DRV8833 (módulo)', 1650, 890, 220, 150, '#F3E5F5', 6),
    ('n20', '4 × N20 (a 5 V)<br>(2 por lado, en paralelo)', 1950, 972, 210, 80, '#FFFFFF', 14),
]

ROSA, GRIS_P, BLANCO = '#FFEBEE', '#ECEFF1', '#FFFFFF'
# Puertos: (id, texto, x, y, ancho, alto, relleno, apagado)
PUERTOS = [
    ('bat_p', '+ (rojo)', 90, 330, 140, 26, ROSA, False),
    ('bat_n', '− (negro)', 90, 380, 140, 26, GRIS_P, False),
    ('xt_e', 'entrada', 290, 330, 75, 26, ROSA, False),
    ('xt_s', 'salida', 365, 330, 75, 26, ROSA, False),
    ('fus_e', 'entrada', 480, 330, 65, 26, ROSA, False),
    ('fus_s', 'salida', 545, 330, 65, 26, ROSA, False),
    ('sh_b', 'lado batería', 650, 330, 80, 26, ROSA, False),
    ('sh_c', 'lado carga', 730, 330, 80, 26, ROSA, False),
    ('ina_p', 'IN+', 652, 486, 76, 26, BLANCO, False),
    ('ina_n', 'IN−', 732, 486, 76, 26, BLANCO, False),
    ('ina_vbs', 'VBS → IN−', 652, 522, 156, 26, BLANCO, False),
    ('ina_vcc', 'VCC ← 3V3 (ESP32)', 652, 558, 156, 26, ROSA, False),
    ('ed_bp', 'B+', 910, 290, 170, 26, ROSA, False),
    ('ed_sen', 'Señal (blanco) → GPIO 41', 910, 370, 170, 26, BLANCO, False),
    ('ed_gnd', 'Negro fino → GND ESP32', 910, 400, 170, 26, GRIS_P, False),
    ('ed_bec', 'BEC 5 V (rojo) → DRV8833', 910, 430, 170, 26, ROSA, False),
    ('ed_ama', 'Amarillo: aislar', 910, 460, 170, 26, '#FAFAFA', True),
    ('ed_fas', '3 fases', 910, 500, 170, 26, BLANCO, False),
    ('ed_bn', 'B−', 910, 554, 170, 26, GRIS_P, False),
    ('et_bp', 'B+', 1130, 290, 170, 26, ROSA, False),
    ('et_sen', 'Señal (blanco) → GPIO 42', 1130, 370, 170, 26, BLANCO, False),
    ('et_gnd', 'Negro fino → GND ESP32', 1130, 400, 170, 26, GRIS_P, False),
    ('et_bec', 'BEC 5 V (rojo) → ESP32', 1130, 430, 170, 26, ROSA, False),
    ('et_ama', 'Amarillo: aislar', 1130, 460, 170, 26, '#FAFAFA', True),
    ('et_fas', '3 fases', 1130, 500, 170, 26, BLANCO, False),
    ('et_bn', 'B−', 1130, 554, 170, 26, GRIS_P, False),
    ('gy_vcc', 'VCC (5 V)', 910, 1000, 170, 26, ROSA, False),
    ('ina_vcc2', 'VCC (3.3 V)', 1130, 1000, 170, 26, ROSA, False),
    ('esp_5v', '5V (también a GY-521)', 1370, 930, 200, 26, ROSA, False),
    ('esp_gnd', 'GND', 1370, 965, 200, 26, GRIS_P, False),
    ('esp_3v3', '3V3 (salida)', 1370, 1000, 200, 26, ROSA, False),
    ('drv_vcc', 'VCC ← 5 V (BEC delantero)', 1660, 930, 200, 26, ROSA, False),
    ('drv_gnd', 'GND', 1660, 965, 200, 26, GRIS_P, False),
    ('drv_out', 'OUT1 a OUT4', 1660, 1000, 200, 26, BLANCO, False),
]

# Cables: (color, grosor, punteado, [puntos])
CABLES = [
    (ROJO, 4, False, [(230, 343), (290, 343)]),
    (ROJO, 4, False, [(440, 343), (480, 343)]),
    (ROJO, 4, False, [(610, 343), (650, 343)]),
    (ROJO, 4, False, [(810, 343), (840, 343), (840, 230), (1215, 230), (1215, 290)]),
    (ROJO, 4, False, [(995, 230), (995, 290)]),
    (NEGRO, 4, False, [(230, 393), (250, 393), (250, 820), (1895, 820)]),
    (NEGRO, 4, False, [(995, 580), (995, 820)]),
    (NEGRO, 4, False, [(1215, 580), (1215, 820)]),
    (NEGRO, 3, False, [(1570, 978), (1605, 978), (1605, 820)]),
    (NEGRO, 3, False, [(1860, 978), (1895, 978), (1895, 820)]),
    (GRIS, 1.5, True, [(690, 356), (690, 486)]),
    (GRIS, 1.5, True, [(770, 356), (770, 486)]),
    (CAFE, 2.5, False, [(910, 513), (885, 513), (885, 860), (995, 860), (995, 880)]),
    (CAFE, 2.5, False, [(1300, 513), (1322, 513), (1322, 860), (1215, 860), (1215, 880)]),
    (MORADO, 3, False, [(1080, 443), (1105, 443), (1105, 790), (1630, 790), (1630, 943),
                        (1660, 943)]),
    (NARANJA, 3, False, [(1300, 443), (1345, 443), (1345, 943), (1370, 943)]),
    (NARANJA, 3, False, [(1080, 1013), (1100, 1013), (1100, 1070), (1345, 1070), (1345, 943)]),
    (AMARILLO, 3, False, [(1300, 1013), (1370, 1013)]),
    (VERDE, 3, False, [(1860, 1013), (1950, 1013)]),
]

REGLAS = (
    '<b>Reglas de la alimentación</b><br>'
    '1. Cada BEC alimenta solo su parte: BEC delantero (morado) → DRV8833 y 4 N20; '
    'BEC trasero (naranja) → ESP32 y 2 GY-521. El INA226 sale del 3V3 de la ESP32.<br>'
    '2. NUNCA unir los dos cables rojos de BEC entre sí.<br>'
    '3. Los BEC son lineales: lo que sobra de la batería se vuelve calor (unos 5 W con la '
    'ESP32, más con los motores). Tocar los ESC tras 5 min de uso: si queman, cambiar a bucks.<br>'
    '4. Con el USB conectado a la ESP32, desconectar el rojo del BEC trasero '
    '(nunca dos fuentes de 5 V a la vez). El GND se deja conectado.<br>'
    '5. XT30 = interruptor general: conectar y desconectar de un solo movimiento; la chispa al '
    'conectar es normal. Aguanta unos 15 A continuos: con succión alta sostenida, usar XT60.'
)

# Textos: (id, html, x, y, ancho, alto, tamaño, color, negrita, caja)
TEXTOS = [
    ('t1', 'Carro Trepador — Alimentación', 40, 20, 900, 34, 22, '#263238', True, None),
    ('t2', 'Rojo: batería 4S (15-17.4 V) · Negro: GND común · Morado: 5 V del BEC delantero '
     '(motores) · Naranja: 5 V del BEC trasero (lógica) · Amarillo: 3.3 V · Café: fases de los '
     'BLDC · Verde: salidas a los N20 · Gris punteado: cables finos de medición',
     40, 58, 2100, 24, 13, '#37474F', False, None),
    ('t3', REGLAS, 1360, 290, 800, 290, 14, '#263238', False, ('#FFFDE7', '#F9A825')),
    ('t4', 'Quitar el shunt R100 del módulo. Los bornes Vin+/Vin− del módulo son los mismos '
     'IN+/IN−.', 640, 630, 230, 60, 12, '#37474F', False, None),
    ('t5', 'GY-521 con 5 V: tienen regulador propio y sus señales quedan en 3.3 V. INA226 siempre '
     'con 3.3 V: no tiene regulador y sus pull-ups pondrían 5 V en la ESP32.',
     40, 900, 780, 50, 13, '#37474F', False, None),
    ('t6', 'DRV8833 con el puente J1 cerrado: EEP queda unido a VCC (5 V) y el chip siempre '
     'activo. No conectar EEP a la ESP32. Capacitor de 100 µF entre VCC y GND y de 100 nF en '
     'cada motor.', 40, 960, 780, 50, 13, '#37474F', False, None),
    ('t7', 'Todas las tierras unidas (GND común). Cargar la batería a 4.20 V por celda mientras '
     'se prueba. Nunca unir los dos rojos de BEC.', 40, 1120, 2100, 30, 13, '#C62828', False,
     None),
]


# ------------------------------------------------------------------ draw.io
def xml_attr(texto):
    return html.escape(texto, quote=True)


def celda(id_, valor, estilo, x, y, w, h):
    return (f'<mxCell id="{id_}" value="{xml_attr(valor)}" style="{estilo}" vertex="1" '
            f'parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" '
            f'as="geometry"/></mxCell>')


def pagina_drawio():
    c = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for id_, titulo, x, y, w, h, relleno, esp in CAJAS:
        c.append(celda(id_, titulo, 'rounded=1;arcSize=4;whiteSpace=wrap;html=1;'
                       f'fillColor={relleno};strokeColor=#455A64;verticalAlign=top;fontStyle=1;'
                       f'fontSize=15;spacingTop={esp};', x, y, w, h))
    for id_, texto, x, y, w, h, relleno, apagado in PUERTOS:
        extra = 'fontColor=#9E9E9E;dashed=1;' if apagado else ''
        c.append(celda(id_, texto, 'rounded=0;whiteSpace=wrap;html=1;'
                       f'fillColor={relleno};strokeColor=#78909C;fontSize=13;spacing=2;{extra}',
                       x, y, w, h))
    for i, (color, grosor, punteado, pts) in enumerate(CABLES):
        (x0, y0), (x1, y1) = pts[0], pts[-1]
        medio = ''.join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
        c.append(f'<mxCell id="c{i}" style="edgeStyle=none;rounded=0;html=1;endArrow=none;'
                 f'strokeColor={color};strokeWidth={grosor};{"dashed=1;" if punteado else ""}" '
                 f'edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                 f'<mxPoint x="{x0}" y="{y0}" as="sourcePoint"/>'
                 f'<mxPoint x="{x1}" y="{y1}" as="targetPoint"/>'
                 f'<Array as="points">{medio}</Array></mxGeometry></mxCell>')
    for id_, texto, x, y, w, h, tam, color, negrita, caja in TEXTOS:
        fondo = (f'fillColor={caja[0]};strokeColor={caja[1]};rounded=1;arcSize=3;'
                 'verticalAlign=top;spacing=12;' if caja else 'verticalAlign=middle;')
        c.append(celda(id_, texto, f'text;html=1;whiteSpace=wrap;fontSize={tam};'
                       f'fontColor={color};align=left;{fondo}'
                       f'{"fontStyle=1;" if negrita else ""}', x, y, w, h))
    return ('<diagram id="alimentacion" name="1. Alimentación"><mxGraphModel grid="1" '
            'gridSize="10" page="0" background="#FFFFFF"><root>' + ''.join(c) +
            '</root></mxGraphModel></diagram>')


def guardar_drawio():
    with open(DRAWIO, encoding='utf-8') as f:
        s = f.read()
    s = re.sub(r'<diagram id="alimentacion".*?</diagram>', lambda _: pagina_drawio(), s,
               count=1, flags=re.S)
    with open(DRAWIO, 'w', encoding='utf-8') as f:
        f.write(s)


# ------------------------------------------------------------------ PNG
FUENTES = '/usr/share/fonts/truetype/dejavu/'


def fuente(tam, negrita=False):
    nombre = 'DejaVuSans-Bold.ttf' if negrita else 'DejaVuSans.ttf'
    return ImageFont.truetype(FUENTES + nombre, int(tam * ESCALA))


def e(v):
    return int(round(v * ESCALA))


def texto_centrado(d, caja, texto, f, color, arriba=None):
    x, y, w, h = caja
    lineas = texto.split('<br>')
    alto_linea = f.size * 1.2
    total = alto_linea * len(lineas)
    y0 = e(y) + e(arriba) if arriba is not None else e(y) + (e(h) - total) / 2
    for i, linea in enumerate(lineas):
        ancho = d.textlength(linea, font=f)
        d.text((e(x) + (e(w) - ancho) / 2, y0 + i * alto_linea), linea, font=f, fill=color)


def envolver(d, texto, f, ancho_max):
    palabras, lineas, actual = texto.split(' '), [], ''
    for p in palabras:
        prueba = (actual + ' ' + p).strip()
        if d.textlength(prueba, font=f) <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    lineas.append(actual)
    return lineas


def dibujar_png():
    img = Image.new('RGB', (e(ANCHO), e(ALTO)), 'white')
    d = ImageDraw.Draw(img)
    for _id, titulo, x, y, w, h, relleno, esp in CAJAS:
        d.rounded_rectangle([e(x), e(y), e(x + w), e(y + h)], radius=e(6), fill=relleno,
                            outline='#455A64', width=2)
        texto_centrado(d, (x, y, w, h), titulo, fuente(13, True), '#263238', arriba=esp)
    for _id, texto, x, y, w, h, relleno, apagado in PUERTOS:
        d.rectangle([e(x), e(y), e(x + w), e(y + h)], fill=relleno, outline='#78909C', width=1)
        texto_centrado(d, (x, y, w, h), texto, fuente(12), '#9E9E9E' if apagado else '#263238')
    for color, grosor, punteado, pts in CABLES:
        pts_e = [(e(x), e(y)) for x, y in pts]
        if punteado:
            for (x0, y0), (x1, y1) in zip(pts_e, pts_e[1:]):
                largo = max(abs(x1 - x0), abs(y1 - y0))
                for k in range(0, largo, 14):
                    t0, t1 = k / largo, min(k + 8, largo) / largo
                    d.line([(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0),
                            (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)], fill=color,
                           width=max(1, e(grosor)))
        else:
            d.line(pts_e, fill=color, width=e(grosor), joint='curve')
    for _id, texto, x, y, w, h, tam, color, negrita, caja in TEXTOS:
        if caja:
            d.rounded_rectangle([e(x), e(y), e(x + w), e(y + h)], radius=e(8), fill=caja[0],
                                outline=caja[1], width=2)
            yy = e(y + 12)
            for parrafo in texto.split('<br>'):
                es_titulo = parrafo.startswith('<b>')
                parrafo = re.sub(r'</?b>', '', parrafo)
                f = fuente(tam + (2 if es_titulo else 0), es_titulo)
                for linea in envolver(d, parrafo, f, e(w - 24)):
                    d.text((e(x + 12), yy), linea, font=f, fill=color)
                    yy += f.size * 1.3
                yy += f.size * 0.35
        else:
            f = fuente(tam, negrita)
            lineas = envolver(d, texto, f, e(w))
            alto = f.size * 1.3 * len(lineas)
            yy = e(y) + (e(h) - alto) / 2
            for linea in lineas:
                d.text((e(x), yy), linea, font=f, fill=color)
                yy += f.size * 1.3
    img.save(PNG)


if __name__ == '__main__':
    guardar_drawio()
    dibujar_png()
    print('Listo:', DRAWIO, PNG)
