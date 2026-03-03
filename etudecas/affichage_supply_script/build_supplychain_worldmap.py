#!/usr/bin/env python3
"""
Build an interactive HTML world map from a geocoded supply graph.

Includes hover overlays for factory nodes using simulation outputs:
- incoming input-stock time series
- outgoing production time series
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


import argparse
import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

NODE_TYPE_STYLES = {
    "supplier_dc": {"name": "Supplier DC", "color": "#1f77b4", "symbol": "circle"},
    "factory": {"name": "Factory", "color": "#d62728", "symbol": "square"},
    "distribution_center": {"name": "Distribution Center", "color": "#ff7f0e", "symbol": "diamond"},
    "customer": {"name": "Customer", "color": "#2ca02c", "symbol": "star"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        "-i",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Input geocoded supply graph JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="etudecas/simulation/result/supply_graph_poc_geocoded_map_with_factory_hover.html",
        help="Output HTML file.",
    )
    parser.add_argument(
        "--title",
        default="Supply Graph POC - Geocoded Map",
        help="HTML page title.",
    )
    parser.add_argument(
        "--sim-input-stocks-csv",
        default="etudecas/simulation/result/production_input_stocks_daily.csv",
        help="Simulation CSV for input material stocks.",
    )
    parser.add_argument(
        "--sim-output-products-csv",
        default="etudecas/simulation/result/production_output_products_daily.csv",
        help="Simulation CSV for output products production.",
    )
    return parser.parse_args()


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def compact_graph_payload(raw: dict[str, Any]) -> dict[str, Any]:
    nodes_in = raw.get("nodes", [])
    edges_in = raw.get("edges", [])
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        raise ValueError("Expected JSON with list fields: nodes and edges.")

    nodes: list[dict[str, Any]] = []
    for node in nodes_in:
        if not isinstance(node, dict):
            continue
        geo = node.get("geo", {}) or {}
        lat = geo.get("lat")
        lon = geo.get("lon")
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            lat = None
            lon = None
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("type", "unknown"),
                "name": node.get("name", ""),
                "location_ID": node.get("location_ID"),
                "country": geo.get("country"),
                "lat": lat,
                "lon": lon,
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in edges_in:
        if not isinstance(edge, dict):
            continue
        items = edge.get("items", [])
        if not isinstance(items, list):
            items = []
        edges.append(
            {
                "id": edge.get("id"),
                "type": edge.get("type", "unknown"),
                "from": edge.get("from"),
                "to": edge.get("to"),
                "items": items,
            }
        )

    node_types = sorted({n.get("type", "unknown") for n in nodes})
    return {
        "schema_version": raw.get("schema_version"),
        "meta": raw.get("meta", {}),
        "nodes": nodes,
        "edges": edges,
        "node_types": node_types,
        "node_type_styles": NODE_TYPE_STYLES,
    }


def build_factory_hover_series(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    items = raw.get("items", []) or []

    factory_ids = {
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "factory"
    }
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}

    item_label: dict[str, str] = {}
    for it in items:
        iid = str(it.get("id"))
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        item_label[iid] = code if code else (name if name else iid)

    in_unit_by_node_item: dict[tuple[str, str], str] = {}
    out_unit_by_node_item: dict[tuple[str, str], str] = {}
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            item_id = str(st.get("item_id"))
            uom = str(st.get("uom") or "").strip()
            if item_id and uom:
                in_unit_by_node_item[(nid, item_id)] = uom
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                uom = str(inp.get("ratio_unit") or "").strip()
                if item_id and uom and (nid, item_id) not in in_unit_by_node_item:
                    in_unit_by_node_item[(nid, item_id)] = uom
            for out in (p.get("outputs") or []):
                item_id = str(out.get("item_id"))
                uom = str(out.get("uom") or "").strip()
                if item_id and uom:
                    out_unit_by_node_item[(nid, item_id)] = uom

    incoming_raw: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_input_stocks_csv.exists():
        with sim_input_stocks_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                val = float(to_float(row.get("stock_before_production")) or 0.0)
                incoming_raw[node_id][item_id].append((day, val))

    outgoing_raw: dict[str, dict[str, list[tuple[int, float, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_output_products_csv.exists():
        with sim_output_products_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                prod = float(to_float(row.get("produced_qty")) or 0.0)
                cum = float(to_float(row.get("cum_produced_qty")) or 0.0)
                outgoing_raw[node_id][item_id].append((day, prod, cum))

    out: dict[str, Any] = {}
    for node_id in sorted(factory_ids):
        incoming = []
        for item_id, pts in sorted(incoming_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            incoming.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": in_unit_by_node_item.get((node_id, item_id), ""),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                }
            )

        outgoing = []
        for item_id, pts in sorted(outgoing_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            outgoing.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": out_unit_by_node_item.get((node_id, item_id), "unit/day"),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                    "cum_values": [p[2] for p in pts_sorted],
                }
            )

        if incoming or outgoing:
            out[node_id] = {
                "node_id": node_id,
                "node_name": node_name.get(node_id, node_id),
                "incoming": incoming,
                "outgoing": outgoing,
            }

    return out


def html_template(title: str, data_json: str) -> str:
    return _lca_public_map_document(f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .title {{
      font-weight: 700;
      font-size: 14px;
      margin-right: 8px;
    }}
    .meta {{
      font-size: 12px;
      color: #475569;
      margin-right: 14px;
    }}
    .box {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    #typeFilters label {{
      margin-right: 8px;
      font-size: 12px;
      white-space: nowrap;
    }}
    #chart {{
      width: 100%;
      height: calc(100vh - 64px);
    }}
    #factoryHoverPanel {{
      position: fixed;
      right: 16px;
      top: 88px;
      width: min(760px, calc(100vw - 32px));
      max-height: calc(100vh - 110px);
      background: rgba(255,255,255,0.98);
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
      z-index: 20;
      overflow: hidden;
      display: none;
      padding: 10px;
    }}
    #factoryHoverPanel.visible {{
      display: block;
    }}
    #factoryHoverTitle {{
      font-size: 13px;
      font-weight: 700;
      margin: 0 0 8px 0;
      color: #0f172a;
    }}
    .factoryHoverGrid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .factoryPlot {{
      height: clamp(160px, calc((100vh - 210px) / 2), 260px);
      border: 1px solid #e2e8f0;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div class="title">{html.escape(title)}</div>
    <div class="meta" id="stats"></div>
    <div class="box">
      <label><input type="checkbox" id="showEdges" checked> Afficher flux</label>
    </div>
    <div class="box" id="typeFilters"></div>
  </div>
  <div id="chart"></div>

  <div id="factoryHoverPanel">
    <div id="factoryHoverTitle"></div>
    <div class="factoryHoverGrid">
      <div id="factoryIncomingChart" class="factoryPlot"></div>
      <div id="factoryOutgoingChart" class="factoryPlot"></div>
    </div>
  </div>

  <script>
    const DATA = {data_json};
    const STYLES = DATA.node_type_styles || {{}};
    const FACTORY_SERIES = DATA.factory_hover_series || {{}};
    const nodeById = Object.fromEntries((DATA.nodes || []).map(n => [n.id, n]));
    const defaultPalette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"];
    let currentFactoryHoverId = null;
    let hoverHandlersBound = false;

    function styleForType(nodeType, idx) {{
      const s = STYLES[nodeType] || {{}};
      return {{
        name: s.name || nodeType,
        color: s.color || defaultPalette[idx % defaultPalette.length],
        symbol: s.symbol || "circle",
      }};
    }}

    function initFilters() {{
      const container = document.getElementById("typeFilters");
      container.innerHTML = "<strong style='font-size:12px;'>Types:</strong>";
      (DATA.node_types || []).forEach((t, idx) => {{
        const style = styleForType(t, idx);
        const lbl = document.createElement("label");
        lbl.innerHTML = `<input class="typeChk" type="checkbox" value="${{t}}" checked> ${{style.name}}`;
        container.appendChild(lbl);
      }});
    }}

    function selectedTypes() {{
      return new Set(Array.from(document.querySelectorAll(".typeChk"))
        .filter(x => x.checked)
        .map(x => x.value));
    }}

    function nodeText(n) {{
      const loc = n.location_ID ? n.location_ID : "n/a";
      const country = n.country ? n.country : "n/a";
      return `${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}<br>Country: ${{country}}<br>Location: ${{loc}}`;
    }}

    function edgeText(e) {{
      const itemCount = Array.isArray(e.items) ? e.items.length : 0;
      const itemPreview = itemCount ? e.items.join(", ") : "n/a";
      return `Edge: ${{e.id}}<br>${{e.from}} -> ${{e.to}}<br>Items (${{itemCount}}): ${{itemPreview}}`;
    }}

    function clamp(value, min, max) {{
      return Math.min(Math.max(value, min), max);
    }}

    function computeGeoView(visibleNodes) {{
      if (!visibleNodes.length) {{
        return {{ scale: 1 }};
      }}
      const lats = visibleNodes.map(n => n.lat);
      const lons = visibleNodes.map(n => n.lon);

      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLon = Math.min(...lons);
      let maxLon = Math.max(...lons);

      const latSpan = Math.max(maxLat - minLat, 0.5);
      const lonSpan = Math.max(maxLon - minLon, 0.5);
      const padLat = Math.max(latSpan * 0.25, 2.0);
      const padLon = Math.max(lonSpan * 0.25, 2.0);

      minLat = clamp(minLat - padLat, -85, 85);
      maxLat = clamp(maxLat + padLat, -85, 85);
      minLon = clamp(minLon - padLon, -180, 180);
      maxLon = clamp(maxLon + padLon, -180, 180);

      const spanLat = Math.max(maxLat - minLat, 1);
      const spanLon = Math.max(maxLon - minLon, 1);
      const effectiveSpan = Math.max(spanLat, spanLon * 0.55);
      const scale = clamp(120 / effectiveSpan, 1.1, 25);

      return {{
        scale: scale,
        center: {{
          lat: (minLat + maxLat) / 2,
          lon: (minLon + maxLon) / 2,
        }}
      }};
    }}

    function buildTraces() {{
      const traces = [];
      const visibleTypes = selectedTypes();
      const showEdges = document.getElementById("showEdges").checked;

      const visibleNodes = (DATA.nodes || []).filter(n =>
        visibleTypes.has(n.type) &&
        Number.isFinite(n.lat) &&
        Number.isFinite(n.lon)
      );
      const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

      (DATA.node_types || []).forEach((nodeType, idx) => {{
        if (!visibleTypes.has(nodeType)) return;
        const style = styleForType(nodeType, idx);
        const subset = visibleNodes.filter(n => n.type === nodeType);
        if (!subset.length) return;
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: style.name,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          text: subset.map(nodeText),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 9,
            color: style.color,
            symbol: style.symbol,
            line: {{ width: 0.6, color: "#111827" }}
          }}
        }});
      }});

      let drawnEdges = 0;
      if (showEdges) {{
        for (const e of (DATA.edges || [])) {{
          const src = nodeById[e.from];
          const dst = nodeById[e.to];
          if (!src || !dst) continue;
          if (!visibleNodeIds.has(src.id) || !visibleNodeIds.has(dst.id)) continue;
          if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) continue;
          if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) continue;
          const itemCount = Array.isArray(e.items) ? e.items.length : 0;
          const width = 1 + Math.min(itemCount, 4);
          traces.push({{
            type: "scattergeo",
            mode: "lines",
            showlegend: false,
            lon: [src.lon, dst.lon],
            lat: [src.lat, dst.lat],
            line: {{ width, color: "#475569" }},
            opacity: 0.65,
            text: edgeText(e),
            hovertemplate: "%{{text}}<extra></extra>",
          }});
          drawnEdges += 1;
        }}
      }}

      document.getElementById("stats").textContent =
        `${{visibleNodes.length}} nodes visibles / ${{(DATA.nodes || []).length}} | ` +
        `${{showEdges ? drawnEdges : 0}} flux affiches / ${{(DATA.edges || []).length}}`;
      return {{ traces, visibleNodes }};
    }}

    function hideFactoryPanel() {{
      const panel = document.getElementById("factoryHoverPanel");
      panel.classList.remove("visible");
      currentFactoryHoverId = null;
    }}

    function chartLayoutBase(titleText, yTitle) {{
      return {{
        title: {{text: titleText, font: {{size: 12}}}},
        margin: {{l: 45, r: 10, t: 32, b: 36}},
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        xaxis: {{title: "Jour", showgrid: true, gridcolor: "#e2e8f0"}},
        yaxis: {{title: yTitle, showgrid: true, gridcolor: "#e2e8f0"}},
        legend: {{orientation: "h", font: {{size: 10}}}},
      }};
    }}

    function showFactoryPanel(factoryId) {{
      const info = FACTORY_SERIES[factoryId];
      if (!info) {{
        hideFactoryPanel();
        return;
      }}

      const panel = document.getElementById("factoryHoverPanel");
      const title = document.getElementById("factoryHoverTitle");
      const incomingDiv = document.getElementById("factoryIncomingChart");
      const outgoingDiv = document.getElementById("factoryOutgoingChart");
      title.textContent = `Factory: ${{info.node_name || factoryId}} (${{factoryId}})`;

      if (currentFactoryHoverId !== factoryId) {{
        const incomingTraces = (info.incoming || []).map((s) => ({{
          type: "scatter",
          mode: "lines+markers",
          name: `${{s.item_label}}${{s.unit ? ` (${{s.unit}})` : ""}}`,
          x: s.days || [],
          y: s.values || [],
          line: {{width: 1.8}},
          marker: {{size: 4}},
          hovertemplate: `${{s.item_label}}<br>Jour=%{{x}}<br>Stock=%{{y:.3f}}${{s.unit ? ` ${{s.unit}}` : ""}}<extra></extra>`,
        }}));

        const outgoingTraces = (info.outgoing || []).map((s) => ({{
          type: "scatter",
          mode: "lines+markers",
          name: `${{s.item_label}}${{s.unit ? ` (${{s.unit}})` : ""}}`,
          x: s.days || [],
          y: s.values || [],
          line: {{width: 1.8}},
          marker: {{size: 4}},
          hovertemplate: `${{s.item_label}}<br>Jour=%{{x}}<br>Production=%{{y:.3f}}${{s.unit ? ` ${{s.unit}}` : ""}}<extra></extra>`,
        }}));

        Plotly.react(
          incomingDiv,
          incomingTraces,
          chartLayoutBase("Matieres entrantes (stock avant production)", "Stock"),
          {{displayModeBar: false, responsive: true}}
        );
        Plotly.react(
          outgoingDiv,
          outgoingTraces,
          chartLayoutBase("Produits sortants (production journaliere)", "Production"),
          {{displayModeBar: false, responsive: true}}
        );
      }}

      currentFactoryHoverId = factoryId;
      panel.classList.add("visible");
    }}

    function bindHoverHandlers() {{
      if (hoverHandlersBound) return;
      const gd = document.getElementById("chart");
      gd.on("plotly_hover", (ev) => {{
        const p = ev && ev.points && ev.points.length ? ev.points[0] : null;
        if (!p || !Array.isArray(p.customdata)) {{
          hideFactoryPanel();
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (nodeType !== "factory") {{
          hideFactoryPanel();
          return;
        }}
        showFactoryPanel(nodeId);
      }});
      gd.on("plotly_unhover", () => {{
        hideFactoryPanel();
      }});
      hoverHandlersBound = true;
    }}

    function draw() {{
      const {{ traces, visibleNodes }} = buildTraces();
      const geoView = computeGeoView(visibleNodes);
      const geoLayout = {{
        scope: "world",
        projection: {{type: "natural earth", scale: geoView.scale || 1}},
        showland: true,
        landcolor: "#eef2f7",
        showcountries: true,
        countrycolor: "#cbd5e1",
        showocean: true,
        oceancolor: "#f8fbff"
      }};
      if (geoView.center) {{
        geoLayout.center = geoView.center;
      }}

      const layout = {{
        margin: {{l: 0, r: 0, t: 0, b: 0}},
        showlegend: true,
        legend: {{orientation: "h"}},
        geo: geoLayout
      }};

      hideFactoryPanel();
      Plotly.newPlot("chart", traces, layout, {{displayModeBar: true, responsive: true}});
      bindHoverHandlers();
    }}

    function init() {{
      initFilters();
      document.getElementById("showEdges").addEventListener("change", draw);
      for (const chk of document.querySelectorAll(".typeChk")) {{
        chk.addEventListener("change", draw);
      }}
      draw();
    }}

    window.addEventListener("load", init);
  </script>
</body>
</html>""")


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    sim_input = Path(args.sim_input_stocks_csv)
    sim_output = Path(args.sim_output_products_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        payload = compact_graph_payload(raw)
        payload["factory_hover_series"] = build_factory_hover_series(raw, sim_input, sim_output)
    except Exception as exc:
        print(f"[ERROR] Unable to read/parse input JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    html_str = html_template(args.title, json.dumps(payload, ensure_ascii=False))
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
