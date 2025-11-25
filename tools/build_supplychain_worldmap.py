#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit un HTML Plotly (carte monde + filtres + flux) directement
à partir du JSON ENRICHI (avec suppliers.{tier1, first_transformation, raw_material}).

Usage:
  python build_from_enriched_json.py \
      --input supplychain_ultimate_ENRICHED_FULL_CLEANED.json \
      --output supplychain_worldmap_from_enriched.html \
      --title "Supply Chain — Enriched JSON"

Aucune dépendance tierce côté Python (Plotly est chargé via CDN dans le HTML).
"""

from __future__ import annotations

# Public spatial rendering boundary.
def _lca_public_map_document(page):
    """Keep operational data and numerical charts available without disclosing map geometry."""
    import json
    import re
    from functools import lru_cache
    from pathlib import PurePosixPath
    GUARD_ID='public-site-selection-v1'

    NOTICE='Les positions géographiques des sites sont retirées de cette version publique.'

    KNOWN_ASSIGN=re.compile('\\b(?:let|var|const)\\s+(DATA(?:_RAW)?|SDD_MAP_PAYLOAD|BASE_DASHBOARD_PAYLOAD)\\s*=\\s*(?=[{\\[])',32)

    PLOT_CALL=re.compile('\\bPlotly\\.(newPlot|react|addFrames)\\s*\\(',32)

    SCRIPTS=re.compile('(<script\\b[^>]*>)(.*?)(</script\\s*>)',50)

    IMAGE_URI=re.compile('data:image/(?:png|jpe?g|webp|gif|bmp|avif|svg\\+xml);base64,[A-Za-z0-9+/=%_\\-]+',34)

    GEO_HOST=re.compile('(?i)(?:https?:)?//(?:nominatim\\.[a-z.]+|(?:www\\.)?openstreetmap\\.org|[a-c]\\.tile\\.openstreetmap\\.org|tile\\.openstreetmap\\.org|maps\\.google\\.[a-z.]+|www\\.google\\.[a-z.]+/maps|maps\\.app\\.goo\\.gl|geocoding-api\\.open-meteo\\.com|maps\\.googleapis\\.com|api\\.geocod\\.io|geocode\\.arcgis\\.com|api\\.opencagedata\\.com|api\\.mapbox\\.com/(?:geocoding|search|directions|styles|tiles)|api-adresse\\.data\\.gouv\\.fr|data\\.geopf\\.fr/(?:geocodage|wmts)|photon\\.komoot\\.io|router\\.project-osrm\\.org|api\\.openrouteservice\\.org|(?:www\\.)?geoportail\\.gouv\\.fr)(?::\\d+)?(?:[/?\\#][^\\s"\'<>\\x60\\\\]*)?',34)

    GEO_TYPES={'densitymapbox', 'densitymap', 'scattermapbox', 'choropleth', 'scattergeo', 'scattermap', 'choroplethmap', 'choroplethmapbox'}

    SPATIAL_LISTS={'geometry', 'geojson', 'country_centroids', 'site_coords', 'tile_url', 'geo_position', 'polyline', 'bbox', 'tiles', 'encoded_polyline', 'country_coords', 'coordinates', 'site_coordinates', 'lnglats', 'geometries', 'map_center', 'geo_bounds', 'coord_map', 'latlngs', 'bounds'}

    COORD_KEY=re.compile('(?:^|_)(?:latitude|longitude|lat|lng|long|lon)(?:$|_)',34)

    PROVIDER=re.compile('\\b(?:folium\\.|leaflet|scattergeo|scattermap(?:box)?|\\.geoPath\\(|L\\.(?:map|marker|circleMarker|polyline)\\(|(?:mapboxgl|maplibregl)\\.Map\\s*\\(|ol\\.Map\\(|cartopy\\.)',34)

    AXIS_GEO=re.compile('\\blongitude\\s*/\\s*fallback\\s*x|\\blatitude\\s*/\\s*fallback\\s*y',34)

    COORD_UID=re.compile('@[-+]?\\d{1,3}(?:\\.\\d+)?\\s*[,;]\\s*[-+]?\\d{1,3}(?:\\.\\d+)?',32)

    B64_PLACEHOLDER=''

    MAP_PATH=re.compile('(?i)(?:^|/)(?:map|.*_map|map_.*|sim_animation|supply_graph_.*|supply_issue_annotated_interactive)\\.html?$',34)

    GUARD='<script id="public-site-selection-v1">\n(function () {\n  const sources = [];\n  function businessTables(){\n    if (!sources.length || !document.body || document.getElementById(\'pub-business-tables\')) return;\n    const pane=document.createElement(\'details\');pane.id=\'pub-business-tables\';\n    const heading=document.createElement(\'summary\');heading.textContent=\'Consulter les données de calcul\';pane.appendChild(heading);\n    const sections=document.createElement(\'select\'), table=document.createElement(\'table\'), status=document.createElement(\'span\'), keys=[];\n    const prev=document.createElement(\'button\'), next=document.createElement(\'button\'), download=document.createElement(\'button\');\n    prev.textContent=\'Précédent\';next.textContent=\'Suivant\';download.textContent=\'Télécharger les données du tableau\';\n    const choose=document.createElement(\'label\');choose.textContent=\'Tableau \';choose.appendChild(sections);\n    [choose,status,prev,next,download,table].forEach(e=>pane.appendChild(e));document.body.prepend(pane);\n    for(const [name,obj] of sources)for(const [k,v] of Object.entries(obj)){\n      if(!v || typeof v!==\'object\' || !Object.keys(v).length)continue;\n      const opt=document.createElement(\'option\');opt.textContent=name+\' / \'+k;sections.appendChild(opt);keys.push(v);\n    }\n    let page=0;\n    function show(){\n      table.replaceChildren();const data=keys[sections.selectedIndex];if(!data)return;\n      const rows=Array.isArray(data)?data:Object.entries(data).map(([key,value])=>({key,value}));\n      const slice=rows.slice(page*20,page*20+20), cols=new Set();\n      const dict=x=>x && typeof x===\'object\'&&!Array.isArray(x)?x:{valeur:x};\n      slice.forEach(x=>Object.keys(dict(x)).slice(0,20).forEach(k=>cols.add(k)));\n      const head=table.createTHead().insertRow();\n      cols.forEach(k=>{const e=document.createElement(\'th\');e.textContent=k;head.appendChild(e);});\n      const body=table.createTBody();\n      slice.forEach(x=>{const r=body.insertRow();cols.forEach(k=>{const y=dict(x)[k];const e=r.insertCell();if(y!==undefined&&y!==null)e.textContent=typeof y===\'object\'?\'[\'+Object.keys(y).length+\' entrées]\':String(y);});});\n      status.textContent=\' \'+rows.length+\' lignes, page \'+(page+1)+\' \';\n      prev.disabled=page===0;next.disabled=(page+1)*20>=rows.length;\n    }\n    sections.onchange=()=>{page=0;show();};prev.onclick=()=>{if(page>0)page--;show();};next.onclick=()=>{page++;show();};\n    download.onclick=()=>{const data=keys[sections.selectedIndex];if(!data)return;const url=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:\'application/json\'}));const a=document.createElement(\'a\');a.href=url;a.download=\'tableau-public.json\';a.click();setTimeout(()=>URL.revokeObjectURL(url),0);};\n    pane.ontoggle=()=>{if(pane.open)show();};\n  }\n  window.__registerPublicResults=function(name,data){sources.push([name,data]);return data;};\n  if(document.readyState===\'loading\')document.addEventListener(\'DOMContentLoaded\',businessTables);else setTimeout(businessTables,0);\n  const pl = window.Plotly;\n  if (!pl || pl.__sitesPrives) return;\n  pl.__sitesPrives = true;\n  const mapTypes = /^(?:scattergeo|scattermap(?:box)?|choropleth(?:map(?:box)?)?|densitymap(?:box)?)$/;\n  for (const method of [\'newPlot\', \'react\', \'addFrames\']) {\n    const render = pl[method];\n    if (typeof render !== \'function\') continue;\n    pl[method] = function (target, traces, layout) {\n      const el = typeof target === \'string\' ? document.getElementById(target) : target;\n      const arr = Array.isArray(traces) ? traces : [];\n      const titles = layout && JSON.stringify([layout.xaxis && layout.xaxis.title, layout.yaxis && layout.yaxis.title]);\n      const geographical = el && (el.dataset.privateSiteView === \'1\' || arr.some(t => mapTypes.test(t.type || \'\')) || (titles && /longitude.*latitude/i.test(titles)) || (layout && (layout.geo || layout.mapbox)));\n      if (!geographical) return render.apply(this, arguments);\n      if (method === \'addFrames\') return Promise.resolve(el);\n      el.dataset.privateSiteView = \'1\';\n      el.replaceChildren();\n      const intro = document.createElement(\'p\'); intro.textContent=\'Les positions géographiques des sites sont retirées de cette version publique.\'; el.appendChild(intro);\n      const list=document.createElement(\'select\'), points=[], seen=new Set();\n      const blank=document.createElement(\'option\'); blank.textContent=\'Sélectionner un élément\'; list.appendChild(blank);\n      arr.forEach((t,curveNumber) => {\n        const labels=[t.ids,t.text,t.hovertext,t.customdata].find(x => Array.isArray(x) && x.length);\n        if (!labels) return;\n        labels.forEach((v,i) => {\n          const label=String(Array.isArray(v)?v[0]:v).replace(/<[^>]+>/g,\' \').trim();\n          if (!label || label.length>180 || seen.has(label)) return;\n          seen.add(label);const o=document.createElement(\'option\');o.textContent=label;list.appendChild(o);\n          points.push({data:t,fullData:t,curveNumber:curveNumber,pointNumber:i,pointIndex:i,customdata:Array.isArray(t.customdata)?t.customdata[i]:undefined,text:label});\n        });\n      });\n      const handlers=el.__siteHandlers || (el.__siteHandlers={});\n      el.on=function(n,f){if(typeof f===\'function\')(handlers[n]||(handlers[n]=new Set())).add(f);return el;};\n      el.removeAllListeners=function(n){if(n) delete handlers[n];else Object.keys(handlers).forEach(k=>delete handlers[k]);return el;};\n      if(points.length){const name=document.createElement(\'label\');name.textContent=\'Élément du réseau \';name.appendChild(list);el.appendChild(name);list.onchange=()=>{const point=points[list.selectedIndex-1];if(point)for(const fn of handlers.plotly_click||[])fn({points:[point]});};}\n      return Promise.resolve(el);\n    };\n  }\n})();\n</script>'

    DECODER=json.JSONDecoder()

    site_keys={}
    def _fallback_string(value):
        def key(match):
            pair=match.group(0)
            if pair not in site_keys:site_keys[pair]="@local-site-"+str(len(site_keys)+1)
            return site_keys[pair]
        return links(COORD_UID.sub(key,value))


    def _json(obj):
        return json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=True).replace('<','\\u003c')


    @lru_cache(maxsize=16384)
    def _compact_key(k):
        return re.sub(r'(?<=[a-z])(?=[A-Z])','_',str(k)).lower()


    def links(text):
        return GEO_HOST.sub('https://localisation.invalid/',text)


    def _structural(v):
        if isinstance(v,list):return [_structural(x) for x in v]
        if isinstance(v,str):
            if v.startswith('data:image/'):return B64_PLACEHOLDER
            return _fallback_string(v) if ('@' in v or '//' in v) else v
        if not isinstance(v,dict):return v
        result={}
        for raw_key,x in v.items():
            k=_compact_key(raw_key)
            key=_fallback_string(raw_key) if '@' in raw_key else raw_key
            if k in SPATIAL_LISTS: result[key]={} if isinstance(x,dict) else [] if isinstance(x,list) else None
            elif COORD_KEY.search(k):result[key]=[] if isinstance(x,list) else None
            else:result[key]=_structural(x)
        return result


    def _clean_obj(obj,path,callback):
        if callback:
            data=callback(path+'.json',_json(obj).encode('utf-8'))
            obj=json.loads(data)
        return _structural(obj)


    def _skip(s,i):
        while i<len(s) and s[i].isspace():i+=1
        return i


    def _plot_args(s,i):
        """Read JSON plot exports only; arbitrary JS arguments are never evaluated."""
        pos=_skip(s,i)
        target,end=DECODER.raw_decode(s,pos)
        if not isinstance(target,str):raise ValueError('nonliteral target')
        pos=_skip(s,end)
        if s[pos:pos+1]!=',':raise ValueError('missing trace delimiter')
        start=_skip(s,pos+1)
        traces,end=DECODER.raw_decode(s,start)
        if not isinstance(traces,list):raise ValueError('nonliteral traces')
        return start,end,traces


    def _is_spatial(plot,layout=None):
        if not isinstance(plot,dict):return False
        if str(plot.get('type','')).lower() in GEO_TYPES or any(k in plot for k in ('lat','lon','longitude','latitude','geojson')):return True
        if isinstance(layout,dict):
            axes=[(layout.get(k) or {}).get('title','') for k in ('xaxis','yaxis')]
            return ('longitude' in str(axes[0]).lower() and 'latitude' in str(axes[1]).lower()) or AXIS_GEO.search(str(axes)) is not None
        return False


    def _plot_data(traces,layout,path,callback,spatial=False):
        clean=[]
        for t in traces:
            if not isinstance(t,dict):clean.append(t);continue
            d=t.copy()
            if spatial or _is_spatial(d,layout):
                for name in ('x','y','z','lat','lon','longitude','latitude','locations','geojson','locationmode','geometry','idsrc','latsrc','lonsrc','xsrc','ysrc'):
                    d.pop(name,None)
                # Normalizes raw XY exports as well, allowing the public selector
                # to claim the chart without leaving a cartesian fallback map.
                d['type']='scattergeo'
            clean.append(d)
        return _clean_obj(clean,path,callback)


    def _safe_layout(layout):
        if not isinstance(layout,dict):return layout
        out=layout.copy()
        for key in ('geo','mapbox','map','images','shapes','annotations','scene'):
            if key in out:out[key]={} if isinstance(out[key],dict) else []
        return out


    def _compressed_patches(s,path,callback):
        import base64
        import gzip
        from io import BytesIO
        marker=re.compile(r'\bconst\s+(DATA_CHUNKED_GZIP_BASE64|DATA_GZIP_BASE64_CHUNKS|DATA_CHUNKED_MANIFEST)\s*=\s*')
        entries={}
        for m in marker.finditer(s):
            value,end=DECODER.raw_decode(s,m.end())
            entries[m[1]]=(m.end(),end,value)
        patches=[]
        if not entries:return patches
        def clean_parts(parts,key):
            if not isinstance(parts,list) or not all(isinstance(q,str) for q in parts):raise ValueError('invalid compressed map fragments')
            packed=base64.b64decode(''.join(parts),validate=True)
            with gzip.GzipFile(fileobj=BytesIO(packed)) as f:
                raw=f.read(512*1024*1024+1)
            if len(raw)>512*1024*1024:raise ValueError('oversize compressed map fragment')
            # Pass decoded records through the caller's ordinary identity/URI policy
            # as well. The surrounding HTML/ZIP pass cannot inspect base64 content.
            logical=path+'!/embedded-'+key+'.json'
            val=json.loads(raw)
            clean=_clean_obj({key:val},logical,callback)[key] if key else _clean_obj(val,logical,callback)
            if clean==val and not (isinstance(val,dict) and any('@' in str(k) for k in val)):return parts,len(raw),len(packed)
            raw2=_json(clean).encode('utf8');packed2=gzip.compress(raw2,compresslevel=6,mtime=0)
            b64=base64.b64encode(packed2).decode('ascii')
            stride=max(len(parts[0]) if parts else 65536,1024)
            return [b64[j:j+stride] for j in range(0,len(b64),stride)],len(raw2),len(packed2)
        if 'DATA_GZIP_BASE64_CHUNKS' in entries:
            a,b,parts=entries['DATA_GZIP_BASE64_CHUNKS'];new,_,_=clean_parts(parts,'')
            patches.append((a,b,_json(new)))
        if 'DATA_CHUNKED_GZIP_BASE64' in entries:
            if 'DATA_CHUNKED_MANIFEST' not in entries:raise ValueError('missing compressed map manifest')
            a,b,blocks=entries['DATA_CHUNKED_GZIP_BASE64'];ma,mb,man=entries['DATA_CHUNKED_MANIFEST']
            if set(blocks)!=set(man):raise ValueError('compressed map manifest and keys mismatch')
            for k,parts in list(blocks.items()):
                blocks[k],n,m=clean_parts(parts,k)
                man[k]['raw_bytes']=n;man[k]['compressed_bytes']=m
            patches.extend([(a,b,_json(blocks)),(ma,mb,_json(man))])
        return patches


    def _script(s,path,callback):
        if not s or 'plotly.js v' in s[:100] or 'Plotly.register(' in s[:120]:return s,False
        patches=_compressed_patches(s,path,callback) if ('DATA_CHUNKED_GZIP_BASE64' in s or 'DATA_GZIP_BASE64_CHUNKS' in s) else []
        found=bool(patches)
        for m in KNOWN_ASSIGN.finditer(s):
            start=m.end()
            try:val,end=DECODER.raw_decode(s,start)
            except (ValueError,RecursionError):continue
            public_data=_json(_clean_obj(val,path,callback))
            # Keep the literal declaration readable to existing extractors and make
            # its numerical tables accessible even when a retired map's filter yields
            # an empty roster. All source-dataset business values remain available.
            if _skip(s,end)<len(s) and s[_skip(s,end)]==';' and 'window.__registerPublicResults(' not in s[end:end+35]:
                public_data+=';window.__registerPublicResults('+json.dumps(m[1])+','+m[1]+')'
            patches.append((start,end,public_data));found=True
        # Plot callbacks in application source use identifiers, unlike the literal
        # JSON arguments in Plotly's standalone and animated HTML exports.
        positions=[]
        for m in PLOT_CALL.finditer(s):
            if any(a<=m.start()<b for a,b,_ in patches):continue
            try:a,b,val=_plot_args(s,m.end())
            except (ValueError,IndexError,RecursionError):continue
            layout=None;ls=le=0
            if m[1]!='addFrames':
                i=_skip(s,b)
                if s[i:i+1]==',':
                    ls=_skip(s,i+1)
                    try:layout,le=DECODER.raw_decode(s,ls)
                    except (ValueError,RecursionError):pass
            positions.append((m[1],a,b,val,layout,ls,le))
        geo_layout=any(any(_is_spatial(t,l) for t in ts) for name,a,b,ts,l,ls,le in positions if name!='addFrames')
        for name,a,b,val,layout,ls,le in positions:
            if name=='addFrames':
                if not (geo_layout or any(any(_is_spatial(t) for t in f.get('data',[])) for f in val if isinstance(f,dict))):continue
                frames=[]
                for frame in val:
                    f=frame.copy()
                    f['data']=_plot_data(f.get('data',[]),None,path,callback,geo_layout)
                    if 'layout' in f:f['layout']=_safe_layout(f['layout'])
                    frames.append(f)
                cleaned=frames
            else:
                if not any(_is_spatial(t,layout) for t in val):continue
                cleaned=_plot_data(val,layout,path,callback)
                if le>ls:patches.append((ls,le,_json(_clean_obj(_safe_layout(layout),path,callback))))
            patches.append((a,b,_json(cleaned)));found=True
        for a,b,val in sorted(patches,reverse=True):s=s[:a]+val+s[b:]
        return s,found


    def _table_html(s):
        """Redact genuine table coordinate columns, keeping adjacent business cells."""
        th=re.compile(r'(<t[hd]\b[^>]*>)(.*?)(</t[hd]>)',re.I|re.S)
        row=re.compile(r'<tr\b[^>]*>.*?</tr\s*>',re.I|re.S)
        def table(m):
            content=m[0];rows=list(row.finditer(content))
            if not rows:return content
            columns=set()
            for r in rows[:4]:
                cells=th.findall(r[0])
                for i,(_,value,_) in enumerate(cells):
                    label=re.sub(r'<[^>]*>','',value).strip().lower().replace(' ','_')
                    if COORD_KEY.search(label) or label in SPATIAL_LISTS:columns.add(i)
            if not columns:return content
            def transform_r(r):
                i=-1
                def transform_c(c):
                    nonlocal i
                    i+=1
                    return c[1]+'—'+c[3] if i in columns and not c[1].lower().startswith('<th') else c[0]
                return th.sub(transform_c,r[0])
            return row.sub(transform_r,content)
        return re.sub(r'<table\b[^>]*>.*?</table\s*>',table,s,flags=re.I|re.S)


    def _fallback_map_page(page,path,callback,note):
        """Unknown active map formats are not forwarded as executable documents."""
        from lxml import html as lhtml, etree
        import html
        safe_tables=[]
        try:
            doc=lhtml.fromstring(page,parser=lhtml.HTMLParser(huge_tree=True))
            for table in doc.xpath('//table[not(ancestor::table)]'):
                rows=[]
                for tr in table.xpath('.//tr'):
                    cs=[''.join(c.itertext()).strip() for c in tr.xpath('./th|./td')]
                    rows.append((cs,bool(tr.xpath('./th'))))
                if not rows:continue
                hide={i for i,c in enumerate(rows[0][0]) if COORD_KEY.search(_compact_key(c).replace(' ','_')) or _compact_key(c) in SPATIAL_LISTS}
                safe_tables.append('<table><tbody>'+''.join('<tr>'+''.join(('<th>' if head else '<td>')+html.escape(_fallback_string(c))+('</th>' if head else '</td>') for i,c in enumerate(cs) if i not in hide)+'</tr>' for cs,head in rows)+'</tbody></table>')
        except (ValueError,etree.ParserError):pass
        if note:note(path,'vue géographique neutralisée ; tableaux HTML hors coordonnées conservés')
        return '<!doctype html><html lang="fr"><meta charset="utf-8"><title>Vue publique</title><body><p>'+NOTICE+'</p>'+''.join(safe_tables)+'</body></html>'


    def _html(path,page,note,callback):
        if NOTICE in page and '<title>Vue publique</title>' in page:return page
        if ('<script id="'+GUARD_ID+'">') in page:
            # A publisher can enrich an already public base map with a fresh result
            # bundle. The original guard must not exempt newly appended raw data.
            exposed=re.search(r"""(?i)["'](?:lat|lon|lng|latitude|longitude|from_lat|from_lon|to_lat|to_lon)["']\s*:\s*(?:[-+]?\d|\[\s*[-+]?\d)|@[-+]?\d{1,3}\.\d+[,;][-+]?\d{1,3}\.\d+""",page)
            if not exposed and not ('DATA_CHUNKED_GZIP_BASE64' in page or 'DATA_GZIP_BASE64_CHUNKS' in page):return page
            page=re.sub(r'<script id="'+GUARD_ID+r'">.*?</script>', '',page,flags=re.S)
        parts=[];last=0;map_handled=False;unknown_renderer=False;real_map_trace=False
        for m in SCRIPTS.finditer(page):
            s=m[2]
            # Plotly's source library contains every mapper as a template for every
            # ordinary stock/histogram export. Only visualizations authored by the
            # project, or real trace objects, determine whether a map is removed.
            vendor=('plotly.js v' in s[:100] or 'Plotly.register(' in s[:120] or 'leaflet' in s[:200].lower() and '@license' in s[:250])
            if vendor:
                parts.append(page[last:m.end()]);last=m.end();continue
            # Avoid parsing generic unrelated DATA tables. Historical data dashboards
            # construct at least one geographic trace in their application code.
            if not ('DATA_CHUNKED_GZIP_BASE64' in s or 'DATA_GZIP_BASE64_CHUNKS' in s or KNOWN_ASSIGN.search(s) and (MAP_PATH.search(path) or PROVIDER.search(s))) and not PLOT_CALL.search(s):
                if re.search(r'\b(?:L\.(?:map|marker|circleMarker|polyline)|d3\.geoPath|mapboxgl\.Map|maplibregl\.Map|ol\.Map)\s*\(',s):unknown_renderer=True
                parts.append(page[last:m.end()]);last=m.end();continue
            try:new,handled=_script(s,path,callback)
            except (ValueError,UnicodeError,RecursionError):
                # Known data payload failed to parse: preserve static tables only;
                # retaining executable map data behind a hidden div leaks positions.
                if MAP_PATH.search(path):return _fallback_map_page(page,path,callback,note)
                raise
            parts.append(page[last:m.start()])
            if handled and not map_handled:parts.append(GUARD)
            map_handled|=handled
            parts.append(m[1]+new+m[3]);last=m.end()
        parts.append(page[last:]);s=''.join(parts)
        if not map_handled and (unknown_renderer or re.search(r'<(?:iframe|object|embed)\b[^>]*(?:openstreetmap|maps\.google|mapbox|geoportail)',s,re.I) or MAP_PATH.search(path) and re.search(r'(?:<canvas\b|scattergeo|geojson|leaflet-container|MapBox)',s,re.I)):
            return _fallback_map_page(page,path,callback,note)
        if map_handled:
            s=IMAGE_URI.sub('',s)
            if note:note(path,'carte géographique retirée ; données et calculs du tableau de bord conservés')
        if re.search(r'<t[hd]\b[^>]*>\s*(?:lat(?:itude)?|lon(?:gitude)?|lng|coordinates|bbox)\b',s,re.I):s=_table_html(s)
        s=re.sub(r'''(?is)\sdata-(?:lat(?:itude)?|lon(?:gitude)?|lng|coordinates|bounds)\s*=\s*(?:"[^"]*"|'[^']*')''','',s)
        return links(s)


    return _html('public_map.html',page,None,None)

def _lca_public_map_file(figure, output, *args, **kwargs):
    from pathlib import Path
    from plotly.io import to_html
    # All historical callers use write_html(file, include_plotlyjs=..., full_html=...).
    kwargs.pop('auto_open', None)
    page = _lca_public_map_document(to_html(figure,*args,**kwargs))
    if hasattr(output, 'write'):
        output.write(page)
    else:
        Path(output).write_text(page, encoding='utf-8')

def _lca_public_tabular_plot(figure):
    """Make geographic network selections readable as a Plotly table."""
    import re
    import plotly.graph_objects as go
    # A table preserves the trace labels and the business metrics held in
    # hover templates. Coordinates never become axes or table values.
    labels=[]
    for trace in figure.data:
        label=getattr(trace,'hovertemplate',None) or getattr(trace,'name',None)
        if label:
            label=re.sub(r'<extra>.*?</extra>|%\{[^}]+\}', '', str(label))
            labels.append(label)
    return go.Figure(data=[go.Table(header={'values':['Éléments du réseau']},cells={'values':[labels]})])

import json, argparse, html, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# ---- Normalisation pays (alias FR/EN courants)
COUNTRY_ALIASES = {
    "france": "France",
    "angleterre": "United Kingdom",
    "royaume-uni": "United Kingdom",
    "uk": "United Kingdom",
    "belgique": "Belgium",
    "allemagne": "Germany",
    "suede": "Sweden",
    "suède": "Sweden",
    "pologne": "Poland",
    "irlande": "Ireland",
    "autriche": "Austria",
    "italie": "Italy",
    "espagne": "Spain",
    "portugal": "Portugal",
    "chine": "China",
    "india": "India",
    "inde": "India",
    "japon": "Japan",
    "thailande": "Thailand",
    "thaïlande": "Thailand",
    "thailand": "Thailand",
    "usa": "United States",
    "etats-unis": "United States",
    "états-unis": "United States",
    "canada": "Canada",
    "brazil": "Brazil",
    "brésil": "Brazil",
    "switzerland": "Switzerland",
    "suisse": "Switzerland",
    "pays-bas": "Netherlands",
    "netherlands": "Netherlands",
}

# ---- Centroïdes pays (approx)
COUNTRY_COORDS = {
    "France": (None, None),
    "United Kingdom": (None, None),
    "Belgium": (None, None),
    "Germany": (None, None),
    "Sweden": (None, None),
    "Poland": (None, None),
    "Ireland": (None, None),
    "Austria": (None, None),
    "Italy": (41.8719, 12.5674),
    "Spain": (40.4637, -3.7492),
    "Portugal": (39.3999, -8.2245),
    "China": (None, None),
    "India": (None, None),
    "Japan": (None, None),
    "Thailand": (None, None),
    "United States": (None, None),
    "Canada": (None, None),
    "Brazil": (-14.2350, -51.9253),
    "Switzerland": (46.8182, 8.2275),
    "Netherlands": (52.1326, 5.2913),
}

TIERS_ORDER = ["primary_material", "raw_material", "first_transformation", "tier1"]

# Couleurs des NŒUDS (markers) par tier
TIER_STYLES = {
    "primary_material":     {"name": "Primary material",      "color": "#7D3C98", "symbol": "diamond"},
    "raw_material":         {"name": "Raw material",          "color": "#1E8449", "symbol": "square"},
    "first_transformation": {"name": "1st transformation",    "color": "#CA6F1E", "symbol": "triangle-up"},
    "tier1":                {"name": "Tier 1",                "color": "#2874A6", "symbol": "circle"},
}

# Libellés de flux et COULEURS des flux (lignes)
FLOW_LABELS = ["Primary → Raw", "Raw → 1st transf.", "1st transf. → Tier 1", "Tier 1 → Safran"]
FLOW_STYLES = {
  "Primary → Raw":        {"color": "#8A2BE2"},  # violet
  "Raw → 1st transf.":    {"color": "#2CA02C"},  # vert
  "1st transf. → Tier 1": {"color": "#FF7F0E"},  # orange
  "Tier 1 → Safran":      {"color": "#1F77B4"},  # bleu
}

def normalize_country(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = (raw or "").strip().lower()
    # capture éventuelle "Name (France)" -> "France"
    if "(" in s and ")" in s:
        inside = s.split("(")[-1].split(")")[0].strip()
        if inside:
            s = inside
    s = s.replace(")", " ").replace("(", " ")
    s = " ".join(s.split())
    if s in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[s]
    return s.title()

def extract_name_and_country(name_field: str, location_field: str) -> Tuple[str, Optional[str], bool]:
    """
    Déduit supplier, country, is_primary depuis name/location.
    - '*' dans le nom => is_primary=True, et on retire '*'.
    - Si 'location' vide, on essaye "Name (France)".
    """
    name = (name_field or "").strip()
    is_primary = False
    if "*" in name or name.endswith("(primary)") or "(primary)" in name.lower():
        is_primary = True
    name_clean = name.replace("*", "").replace("(primary)", "").replace("(Primary)", "").strip()

    country = normalize_country(location_field or "")
    if not country:
        # Essaye de déduire depuis le nom "Foo (France)"
        if "(" in name and ")" in name:
            inside = name.split("(")[-1].split(")")[0].strip()
            country = normalize_country(inside)

    return name_clean, country, is_primary

def load_enriched(path: Path) -> List[Dict[str, Any]]:
    """
    Charge le JSON enrichi (liste d'objets) et fabrique DES 'records' utilisables par la visualisation :
      { system, component, tiers: { tier1:[{supplier,country,is_primary},...], ... } }
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        raw = raw["records"]
    if not isinstance(raw, list):
        raise ValueError("Le JSON enrichi doit être une liste (ou un objet avec 'records').")

    records = []
    for rec in raw:
        if not isinstance(rec, dict):
            continue
        system = (rec.get("system") or "").strip()
        component = (rec.get("component") or "").strip()
        suppliers = rec.get("suppliers") or {}

        tiers_out = {k: [] for k in TIERS_ORDER}
        for tier in TIERS_ORDER:
            lst = suppliers.get(tier, []) or []
            if not isinstance(lst, list):
                continue
            for entry in lst:
                if isinstance(entry, dict):
                    nm = entry.get("name") or entry.get("supplier") or ""
                    loc = entry.get("location") or entry.get("country") or ""
                    is_p = bool(entry.get("is_primary", False))
                    lat = entry.get("lat")
                    lon = entry.get("lon")
                    # Normalise à partir de name/location
                    supplier, country, is_star = extract_name_and_country(nm, loc)
                    is_primary = is_p or is_star
                    lat = float(lat) if isinstance(lat, (int, float, str)) and str(lat).strip() not in ("", "None") else None
                    lon = float(lon) if isinstance(lon, (int, float, str)) and str(lon).strip() not in ("", "None") else None
                else:
                    # chaîne brute
                    supplier, country, is_primary = extract_name_and_country(str(entry), "")
                    lat = lon = None

                if not supplier:
                    continue
                # ignore si pays inconnu ET impossible de déduire -> la carte ne saura pas placer
                if country is None:
                    continue
                tiers_out[tier].append({
                    "supplier": supplier,
                    "country": country,
                    "is_primary": is_primary,
                    "lat": lat,
                    "lon": lon,
                })

        records.append({"system": system, "component": component, "tiers": tiers_out})
    return records

def build_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    systems = ["All"]
    components = ["All"]
    for r in records:
        s = r.get("system") or ""
        c = r.get("component") or ""
        if s and s not in systems: systems.append(s)
        if c and c not in components: components.append(c)
    return {
        "tiers": TIERS_ORDER,
        "tier_styles": TIER_STYLES,
        "safran": {"lat": None, "lon": None},
        "systems": systems,
        "components": components,
        "records": records,
        "flow_labels": FLOW_LABELS,
        "flow_styles": FLOW_STYLES,
        "country_coords": COUNTRY_COORDS,
    }

def html_template(title: str, data_json: str) -> str:
    return _lca_public_map_document(f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
 body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; }}
 .toolbar {{
   display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
   padding: 12px 16px; border-bottom: 1px solid #e5e5e5; background: #fafafa;
   position: sticky; top: 0; z-index: 5;
 }}
 label {{ font-size: 12px; color: #333; margin-right: 4px; }}
 select, input[type="checkbox"] {{ padding: 6px 8px; font-size: 13px; border: 1px solid #ccc; border-radius: 6px; background: white; }}
 #chart {{ width: 100%; height: calc(100vh - 64px); }}
 .spacer {{ flex: 1; }}
</style>
</head>
<body>
<div class="toolbar">
  <div>
    <label for="systemSel">Système</label>
    <select id="systemSel"></select>
  </div>
  <div>
    <label for="componentSel">Composant</label>
    <select id="componentSel"></select>
  </div>
  <div>
    <label>Niveaux</label>
    <label><input type="checkbox" class="tierChk" value="primary_material"> Primary</label>
    <label><input type="checkbox" class="tierChk" value="raw_material" checked> Raw</label>
    <label><input type="checkbox" class="tierChk" value="first_transformation" checked> 1st transf.</label>
    <label><input type="checkbox" class="tierChk" value="tier1" checked> Tier 1</label>
  </div>
  <div>
    <label>Flux</label>
    <label><input type="checkbox" class="flowChk" value="Primary → Raw" checked> P→R</label>
    <label><input type="checkbox" class="flowChk" value="Raw → 1st transf." checked> R→1st</label>
    <label><input type="checkbox" class="flowChk" value="1st transf. → Tier 1" checked> 1st→T1</label>
    <label><input type="checkbox" class="flowChk" value="Tier 1 → Safran" checked> T1→Safran</label>
  </div>
  <div>
    <label><input type="checkbox" id="onlyPrimary"> Fournisseurs principaux uniquement</label>
  </div>
  <div class="spacer"></div>
</div>
<div id="chart"></div>

<script>
const DATA = {data_json};

// === Styles des flux par catégorie ===
const FLOW_STYLES = DATA.flow_styles || {{}};

// Échelle d’épaisseur (linéaire) — tu pourras adapter
function scaleWidth(value, vmin, vmax, wmin=0.8, wmax=6) {{
  if (!isFinite(value)) return wmin;
  if (vmax <= vmin) return wmin;
  const r = (value - vmin) / (vmax - vmin);
  return wmin + r * (wmax - wmin);
}}

const countryCoords = DATA.country_coords || {{}};
function getLatLon(supplier) {{
  if (!supplier) return null;
  const lat = supplier.lat;
  const lon = supplier.lon;
  if (typeof lat === "number" && typeof lon === "number" && isFinite(lat) && isFinite(lon)) {{
    return {{lat, lon}};
  }}
  const country = supplier.country;
  if (!country) return null;
  const coords = countryCoords[country];
  return coords ? {{lat: coords[0], lon: coords[1]}} : null;
}}

function fillSelect(sel, options) {{
  sel.innerHTML = "";
  for (const opt of options) {{
    const o = document.createElement("option");
    o.value = opt; o.textContent = opt;
    sel.appendChild(o);
  }}
}}

function currentFilters() {{
  const sys = document.getElementById("systemSel").value;
  const comp = document.getElementById("componentSel").value;
  const tierChks = Array.from(document.querySelectorAll(".tierChk")).filter(x => x.checked).map(x => x.value);
  const flowChks = Array.from(document.querySelectorAll(".flowChk")).filter(x => x.checked).map(x => x.value);
  const onlyPrimary = document.getElementById("onlyPrimary").checked;
  return {{ system: sys, component: comp, tiers: tierChks, flows: flowChks, onlyPrimary }};
}}

function recordMatches(rec, filters) {{
  if (filters.system !== "All" && rec.system !== filters.system) return false;
  if (filters.component !== "All" && rec.component !== filters.component) return false;
  return true;
}}

function buildTraces() {{
  const filters = currentFilters();
  const traces = [];
  const lines = [];

  // Points par niveau
  for (const tier of DATA.tiers) {{
    if (!filters.tiers.includes(tier)) continue;
    const style = DATA.tier_styles[tier] || {{}};
    const xs = [], ys = [], texts = [];

    for (const rec of DATA.records) {{
      if (!recordMatches(rec, filters)) continue;
      const suppliers = (rec.tiers && rec.tiers[tier]) ? rec.tiers[tier] : [];
      for (const s of suppliers) {{
        if (filters.onlyPrimary && !s.is_primary) continue;
        const loc = getLatLon(s);
        if (!loc) continue;
        xs.push(loc.lon); ys.push(loc.lat);
        texts.push(`${{s.supplier || "?"}} — ${{s.country || "?"}}\\n[${{rec.system}}] ${{rec.component}}`);
      }}
    }}

    traces.push({{
      type: "scattergeo",
      mode: "markers",
      lon: xs, lat: ys, text: texts,
      name: style.name || tier,
      marker: {{
        size: 8,
        color: style.color || "#666",
        symbol: style.symbol || "circle",
        line: {{width: 0.5, color: "#333"}}
      }}
    }});
  }}

  // Lignes/flux avec agrégation par paire de pays
  function addLines(fromTier, toTier, label) {{
    if (!currentFilters().flows.includes(label)) return;

    const style = FLOW_STYLES[label] || {{ color: "#888" }};
    const edgeMap = new Map(); // key: "lat1,lon1->lat2,lon2" ; val: {{from,to,value}}

    for (const rec of DATA.records) {{
      if (!recordMatches(rec, currentFilters())) continue;

      const fromList = (rec.tiers && rec.tiers[fromTier]) ? rec.tiers[fromTier] : [];
      const toList   = (toTier === "safran")
        ? [{{ supplier: "Safran", country: "France" }}]
        : ((rec.tiers && rec.tiers[toTier]) ? rec.tiers[toTier] : []);

      for (const f of fromList) {{
        if (currentFilters().onlyPrimary && !f.is_primary) continue;
        const fLoc = getLatLon(f);
        if (!fLoc) continue;

        // Option “units” future : si tu ajoutes une quantité (f.units), on la sommera ici
        const fUnits = (typeof f.units === "number" && f.units > 0) ? f.units : 1;

        for (const t of toList) {{
          if (toTier !== "safran" && currentFilters().onlyPrimary && !t.is_primary) continue;
          const tLoc = (toTier === "safran") ? {{lat: DATA.safran.lat, lon: DATA.safran.lon}} : getLatLon(t);
          if (!tLoc) continue;

          const key = `${{fLoc.lat.toFixed(3)}},${{fLoc.lon.toFixed(3)}}->${{tLoc.lat.toFixed(3)}},${{tLoc.lon.toFixed(3)}}`;
          const inc = fUnits; // aujourd’hui: 1 par edge ; demain: mets ta vraie quantité

          if (!edgeMap.has(key)) {{
            edgeMap.set(key, {{ from: fLoc, to: tLoc, value: 0 }});
          }}
          edgeMap.get(key).value += inc;
        }}
      }}
    }}

    // Min/max pour l'échelle d'épaisseur
    let vmin = Infinity, vmax = -Infinity;
    edgeMap.forEach(({{value}}) => {{ if (value < vmin) vmin = value; if (value > vmax) vmax = value; }});
    if (!isFinite(vmin)) {{ vmin = 1; vmax = 1; }}

    // Traces de lignes
    edgeMap.forEach(({{from, to, value}}) => {{
      const width = scaleWidth(value, vmin, vmax, 0.8, 6);
      lines.push({{
        type: "scattergeo",
        mode: "lines",
        lon: [from.lon, to.lon],
        lat: [from.lat, to.lat],
        line: {{ width, color: style.color }},
        opacity: 0.9,
        hoverinfo: "text",
        text: `${{label}} — qty: ${{value}}`,
        showlegend: false
      }});
    }});
  }}

  addLines("primary_material", "raw_material", "Primary → Raw");
  addLines("raw_material", "first_transformation", "Raw → 1st transf.");
  addLines("first_transformation", "tier1", "1st transf. → Tier 1");
  addLines("tier1", "safran", "Tier 1 → Safran");

  return traces.concat(lines);
}}

function draw() {{
  const traces = buildTraces();
  const layout = {{
    geo: {{
      scope: "world",
      projection: {{ type: "natural earth" }},
      showland: true, landcolor: "#f0f0f0",
      subunitwidth: 1, countrywidth: 1,
      subunitcolor: "#dcdcdc", countrycolor: "#dcdcdc"
    }},
    margin: {{l:0,r:0,t:0,b:0}},
    legend: {{orientation: "h"}}
  }};
  Plotly.newPlot("chart", traces, layout, {{displayModeBar: true, responsive: true}});
}}

function refreshDependentSelects() {{
  const sys = document.getElementById("systemSel").value;
  const comp = document.getElementById("componentSel").value;
  const comps = ["All"], syses = ["All"];
  for (const rec of DATA.records) {{
    if (sys === "All" || rec.system === sys) {{
      if (rec.component && !comps.includes(rec.component)) comps.push(rec.component);
    }}
    if (comp === "All" || rec.component === comp) {{
      if (rec.system && !syses.includes(rec.system)) syses.push(rec.system);
    }}
  }}
  fillSelect(document.getElementById("componentSel"), comps);
  fillSelect(document.getElementById("systemSel"), syses);
  if (syses.includes(sys)) document.getElementById("systemSel").value = sys;
  if (comps.includes(comp)) document.getElementById("componentSel").value = comp;
}}

function initUI() {{
  fillSelect(document.getElementById("systemSel"), DATA.systems || ["All"]);
  fillSelect(document.getElementById("componentSel"), DATA.components || ["All"]);
  document.getElementById("systemSel").addEventListener("change", ()=>{{ refreshDependentSelects(); draw(); }});
  document.getElementById("componentSel").addEventListener("change", ()=>{{ refreshDependentSelects(); draw(); }});
  for (const el of document.querySelectorAll(".tierChk, .flowChk, #onlyPrimary")) {{ el.addEventListener("change", draw); }}
  draw();
}}
window.addEventListener("load", initUI);
</script>
</body>
</html>""")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", "-i", required=True, help="Chemin du JSON ENRICHI (avec suppliers.*)")
    p.add_argument("--output", "-o", required=True, help="HTML de sortie")
    p.add_argument("--title", default="Supply Chain — Enriched JSON")
    args = p.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    try:
        records = load_enriched(in_path)
    except Exception as e:
        print(f"[ERREUR] Lecture/parse JSON enrichi: {e}", file=sys.stderr)
        sys.exit(1)

    # Petit log de contrôle
    n_nodes = sum(len(r["tiers"].get(t, [])) for r in records for t in TIERS_ORDER)
    print(f"[INFO] {len(records)} records, {n_nodes} fournisseurs positionnables.")

    data = build_data(records)
    html_str = html_template(args.title, json.dumps(data, ensure_ascii=False))
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML généré → {out_path.resolve()}")

if __name__ == "__main__":
    main()
