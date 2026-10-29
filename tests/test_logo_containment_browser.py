"""Opt-in real-browser component/theme checks; no customer data or OBS session.

Set CSRN_LOGO_BROWSER_EXECUTABLE to a Chromium executable. Optionally set
CSRN_LOGO_EVIDENCE_DIR to retain screenshots of synthetic boundary fixtures.
"""
from __future__ import annotations

import base64
import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from logo_service import LogoService

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not os.environ.get('CSRN_LOGO_BROWSER_EXECUTABLE'),
    reason='Opt-in Chromium component verification',
)


def png_uri(image):
    output = io.BytesIO()
    image.save(output, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


def test_logo_components_and_frozen_theme_geometry():
    from playwright.sync_api import sync_playwright

    square = Image.new('RGBA', (100, 100), '#C9A227')
    ImageDraw.Draw(square).rectangle((8, 8, 91, 91), fill='#B5121B')
    fixtures = [square, Image.new('RGBA', (400, 80), '#C9A227'),
                Image.new('RGBA', (80, 400), '#C9A227')]
    circle = Image.new('RGBA', (100, 100))
    ImageDraw.Draw(circle).ellipse((0, 0, 99, 99), fill='#C9A227')
    margins = Image.new('RGBA', (200, 200))
    margins.alpha_composite(square, (50, 50))
    fixtures.extend([circle, margins])
    sources = [png_uri(LogoService.fit_logo(image, 256)) for image in fixtures]
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 80"><rect width="400" height="80" fill="#c9a227"/></svg>'
    sources.append('data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode())
    evidence = Path(os.environ.get('CSRN_LOGO_EVIDENCE_DIR', '/tmp/csrn-logo-evidence'))
    evidence.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ['CSRN_LOGO_BROWSER_EXECUTABLE'], args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1920,'height':1080})
        # Use actual application styles and selectors in an isolated harness.
        page.set_content('''<body><h2>Synthetic boundary fixture — component verification</h2>
        <div class="branding-preview-grid"><div class="logo-preview-card"><img id="schoolLogoPreview" style="display:block"><span>Processed candidate</span></div>
        <div class="broadcast-brand-preview"><div class="preview-logo-shell"><img id="schoolBroadcastLogo" style="display:block"></div><strong>Broadcast preview</strong></div></div>
        <div class="branding-logo-candidate"><img id="candidate"><span>Source candidate</span></div>
        <div id="scorebug"></div><div id="csrnProductionThemeLayout" class="package-heritage-newspaper"><div class="hp-team-mark"><img id="heritage"></div></div>''')
        for name in ('style.css','csrn-scorebug-engine.css','csrn-heritage-press-engine.css','csrn-production-theme-runtime.css'):
            page.add_style_tag(path=str(ROOT/'static'/name))
        # The discovery candidate rule is inline in the real team manager.
        import re
        template = (ROOT/'templates/index.html').read_text()
        for rules in re.findall(r'<style[^>]*>(.*?)</style>', template, re.S):
            if '.branding-logo-candidate' in rules:
                page.add_style_tag(content=rules)
        page.add_script_tag(path=str(ROOT/'static/csrn-scorebug-engine.js'))
        baseline = os.environ.get('CSRN_LOGO_BASELINE_ROOT')
        if baseline:
            import runpy
            legacy = runpy.run_path(str(Path(baseline)/'logo_service.py'))['LogoService']
            before = png_uri(legacy.normalize_round_logo(square, 256))
            old_style = page.add_style_tag(content='.logo-preview-card img{border-radius:50%}')
            page.evaluate("src=>{document.querySelectorAll('img').forEach(i=>i.src=src);CSRNScorebugEngine.render(document.getElementById('scorebug'),'modern',{home:{logo:src},visitor:{logo:src}})}", before)
            page.wait_for_function("[...document.images].every(i=>i.complete && i.naturalWidth>0)")
            page.screenshot(path=str(evidence/'components-before.png'))
            old_style.evaluate('(node)=>node.remove()')
        for index, source in enumerate(sources):
            page.evaluate('''src=>{
              document.querySelectorAll('img').forEach(img=>img.src=src);
              CSRNScorebugEngine.render(document.getElementById('scorebug'),'modern',{
                home:{name:'BOUNDARY',logo:src},visitor:{name:'TEST',logo:src}});
            }''', source)
            page.wait_for_function("[...document.images].every(i=>i.complete && i.naturalWidth>0)")
            for selector in ('#schoolLogoPreview','#schoolBroadcastLogo','#candidate','#homeLogo','#heritage'):
                assert page.locator(selector).evaluate("i=>getComputedStyle(i).objectFit") == 'contain'
            if index == 0:
                # Assert the actual rendered gold corners survive the candidate
                # preview's former border-radius mask.
                png = page.locator('#schoolLogoPreview').screenshot()
                image = Image.open(io.BytesIO(png)).convert('RGB')
                assert image.getpixel((16,16)) == (201,162,39)
                page.screenshot(path=str(evidence/'components-after.png'))
        # Run the real frozen theme engines with the new shared rendition.
        for name in ('broadcast-layout','friday-night-stadium','eight-bit-gameday','heritage-press'):
            page.add_script_tag(path=str(ROOT/'static'/f'csrn-{name}-engine.js'))
            if name != 'broadcast-layout':
                page.add_style_tag(path=str(ROOT/'static'/f'csrn-{name}-engine.css'))
        for engine in ('CSRNFridayNightStadiumEngine','CSRNEightBitGamedayEngine','CSRNHeritagePressEngine'):
            dimensions = []
            for source in (sources[0],sources[1],sources[2]):
                dimensions.append(page.evaluate('''({engine,src})=>{
                  const root=document.getElementById('csrnProductionThemeLayout');
                  const e=window[engine];
                  e.renderPackage(root,e.packageId,'football',{home:{name:'BOUNDARY',logo:src},visitor:{name:'TEST',logo:src}});
                  return [root.getBoundingClientRect().width,root.getBoundingClientRect().height];
                }''', {'engine':engine,'src':source}))
            assert dimensions[0] == dimensions[1] == dimensions[2]
            assert dimensions[0] == [1920,1080]
            page.evaluate('''({engine,src})=>{
                const e=window[engine];e.renderPackage(document.getElementById('csrnProductionThemeLayout'),e.packageId,'football',{home:{name:'BOUNDARY',logo:src},visitor:{name:'TEST',logo:src}});
            }''', {'engine':engine,'src':sources[0]})
            page.wait_for_function("[...document.querySelectorAll('#csrnProductionThemeLayout [data-bind$=\".logo\"] img')].every(i=>i.complete && i.naturalWidth>0)")
            page.locator('#csrnProductionThemeLayout').screenshot(path=str(evidence/f'{engine}-after.png'))
        browser.close()
