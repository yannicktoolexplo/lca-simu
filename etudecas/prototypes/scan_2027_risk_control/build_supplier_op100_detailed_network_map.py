#!/usr/bin/env python3
"""Build a standalone, detailed op_100 supplier-network HTML without simulation."""

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
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping


EXPECTED_PACKAGE_SIGNATURE = (
    "0231b89f05b07d739fafac72478926bfb23d6cfd2edf8f659b786cdaa8d1367a"
)
EXPECTED_CAMPAIGN_SIGNATURE = (
    "fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598"
)
SOURCE_FILES = {
    "manifest": "manifest_paquet_op_100_30_sur_30.json",
    "summary": "bilan_provisoire_op_100_30_sur_30.json",
    "lanes": "resultats_descriptifs_par_voie_op_100_30_sur_30.csv",
    "cases": "mesures_simulees_1110_op_100_30_sur_30.csv",
}
ENTRYPOINT = "OUVRIR_CARTE_DETAILLEE_OP_100_30_SUR_30.html"


class DetailedMapError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise DetailedMapError(f"JSON hors contrat : {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def as_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def validate_source(source_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    paths = {key: source_dir / name for key, name in SOURCE_FILES.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise DetailedMapError("Sources absentes : " + ", ".join(missing))
    manifest = read_json(paths["manifest"])
    if manifest.get("package_signature") != EXPECTED_PACKAGE_SIGNATURE:
        raise DetailedMapError("Le paquet op_100 30/30 n'est pas celui validé.")
    if manifest.get("campaign_signature") != EXPECTED_CAMPAIGN_SIGNATURE:
        raise DetailedMapError("La campagne source n'est pas celle attendue.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping):
        raise DetailedMapError("Index des sorties source absent.")
    for key in ("summary", "lanes", "cases"):
        name = SOURCE_FILES[key]
        record = outputs.get(name)
        if not isinstance(record, Mapping) or sha256_file(paths[key]) != record.get(
            "sha256"
        ):
            raise DetailedMapError(f"Empreinte source invalide : {name}")
    return {"manifest": manifest, "paths": paths}


def build_payload(source_dir: Path, lane_reference: Path) -> dict[str, Any]:
    validated = validate_source(source_dir)
    if not lane_reference.is_file():
        raise DetailedMapError(f"Référence des voies absente : {lane_reference}")
    stats = read_csv(validated["paths"]["lanes"])
    cases = read_csv(validated["paths"]["cases"])
    references = read_csv(lane_reference)
    if len(stats) != 36 or len(references) != 18 or len(cases) != 1110:
        raise DetailedMapError(
            f"Comptages inattendus : voies={len(references)}, statistiques={len(stats)}, cas={len(cases)}"
        )
    reference_by_lane = {row["chain_id"]: row for row in references}
    sample_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    sample_units: dict[tuple[str, str], list[float]] = defaultdict(list)
    sample_production: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in cases:
        if row.get("stage") != "incident":
            continue
        key = (row["mechanism"], row["lane_id"])
        sample_values[key].append(as_float(row.get("impact_service_loss_fed_product_pp")))
        sample_units[key].append(as_float(row.get("impact_on_due_loss_fed_product_qty")))
        sample_production[key].append(
            as_float(row.get("impact_production_loss_fed_product_qty"))
        )
    lanes: list[dict[str, Any]] = []
    for row in stats:
        lane_id = row["lane_id"]
        reference = reference_by_lane.get(lane_id)
        if reference is None:
            raise DetailedMapError(f"Voie sans référence physique : {lane_id}")
        key = (row["mechanism"], lane_id)
        samples = sample_values[key]
        if len(samples) != 30:
            raise DetailedMapError(f"La voie {key} ne contient pas 30 répétitions.")
        lanes.append(
            {
                "mechanism": row["mechanism"],
                "lane_id": lane_id,
                "supplier": row["supplier_id"],
                "item": row["item_id"].removeprefix("item:"),
                "plant": row["dst_node_id"],
                "product": row["target_product_id"],
                "lead_days": as_float(reference.get("planned_lead_days")),
                "reference_qty": as_float(reference.get("reference_total_shipped_qty")),
                "reference_shipment_days": as_int(reference.get("reference_shipment_day_count")),
                "mean_loss": as_float(row.get("service_loss_mean_pp")),
                "median_loss": as_float(row.get("service_loss_median_pp")),
                "p10": as_float(row.get("service_loss_p10_pp")),
                "p90": as_float(row.get("service_loss_p90_pp")),
                "max_loss": as_float(row.get("service_loss_max_pp")),
                "affected_count": as_int(row.get("positive_service_effect_count")),
                "exercised_count": as_int(row.get("physical_exercise_count")),
                "late_units_mean": as_float(row.get("on_due_units_lost_mean")),
                "production_loss_mean": as_float(
                    row.get("production_not_released_mean_qty")
                ),
                "backlog_load_mean": as_float(
                    row.get("backlog_qty_days_per_demand_unit_mean")
                ),
                "samples": [round(value, 6) for value in samples],
                "late_samples": [round(value, 3) for value in sample_units[key]],
                "production_samples": [
                    round(value, 3) for value in sample_production[key]
                ],
            }
        )
    suppliers = sorted({row["supplier"] for row in lanes})
    transport = [row for row in lanes if row["mechanism"] == "transport_delay"]
    shortfall = [
        row for row in lanes if row["mechanism"] == "planned_delivery_shortfall"
    ]
    sensitive = [row for row in transport if row["mean_loss"] > 0]
    return {
        "schema_version": "etudecas.supplier_v8.op100_detailed_network_map.v1",
        "campaign_signature": EXPECTED_CAMPAIGN_SIGNATURE,
        "source_package_signature": EXPECTED_PACKAGE_SIGNATURE,
        "operating_point": "op_100",
        "simulation_count": 30,
        "case_count": 1110,
        "incident_count": 1080,
        "lane_count": len(references),
        "supplier_count": len(suppliers),
        "lanes": lanes,
        "headline": {
            "sensitive_transport_lanes": len(sensitive),
            "shortfall_absorbed_lanes": sum(row["mean_loss"] == 0 for row in shortfall),
            "top_transport": [row["lane_id"] for row in sorted(transport, key=lambda x: -x["mean_loss"])[:4]],
            "transport_mean_loss_across_lanes": mean(row["mean_loss"] for row in transport),
        },
    }


def render_html(payload: Mapping[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    return _lca_public_map_document("""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Carte détaillée du réseau — op_100 — 30/30</title>
<style>
:root{--navy:#092b50;--blue:#1768c4;--sky:#eaf3ff;--green:#11845f;--amber:#ef9f1a;--red:#ce3e35;--ink:#14263a;--muted:#60758b;--line:#d5e1ec;--paper:#fff;--bg:#edf3f8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,Segoe UI,Arial,sans-serif}header{background:linear-gradient(125deg,#082947,#154f82);color:#fff;padding:30px max(24px,4vw)}header h1{margin:7px 0;font-size:clamp(28px,4vw,46px)}header p{max-width:1050px;margin:6px 0;color:#dbeafe}.tag{display:inline-block;padding:6px 10px;border-radius:999px;background:#ffffff20;border:1px solid #ffffff40;font-size:12px;font-weight:800;letter-spacing:.05em}.wrap{max-width:1500px;margin:auto;padding:20px}.notice{background:#fff7e6;border-left:5px solid var(--amber);padding:14px 17px;border-radius:10px;margin-bottom:16px}.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:11px;margin:15px 0}.kpi,.panel,.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:0 7px 20px #183b5b0d}.kpi{padding:15px}.kpi strong{display:block;font-size:28px;color:var(--navy)}.kpi span{font-size:12px;color:var(--muted)}.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:end;padding:14px;margin:15px 0;background:#fff;border:1px solid var(--line);border-radius:14px}.controls label{font-size:12px;font-weight:800;color:var(--muted)}select,button{display:block;margin-top:5px;border:1px solid #b9cada;border-radius:9px;padding:9px 11px;background:#fff;color:var(--ink)}button{cursor:pointer}.layout{display:grid;grid-template-columns:minmax(700px,2fr) minmax(330px,1fr);gap:14px}.panel{padding:14px;overflow:hidden}.panel h2,.card h2{margin:0 0 5px}.sub{color:var(--muted);font-size:13px;margin:0 0 10px}.map-scroll{overflow:auto;max-height:900px}svg{display:block;width:100%;min-width:900px;height:auto;background:linear-gradient(#fbfdff,#f5f9fd);border:1px solid var(--line);border-radius:12px}.lane{fill:none;cursor:pointer;transition:.15s}.lane:hover,.lane.selected{stroke:#7b3fc6!important;stroke-width:8!important;opacity:1!important}.node rect{fill:#fff;stroke:#b8cbdd;stroke-width:1.5}.node text{font-size:12px;fill:var(--ink);font-weight:700}.plant rect{fill:#e9f3ff;stroke:#1768c4}.product rect{fill:#e7f7f0;stroke:#11845f}.detail{padding:17px;position:sticky;top:10px;min-height:500px}.badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:850}.badge.sim{background:#e5efff;color:#1456a0}.badge.high{background:#fde8e6;color:#a12822}.badge.abs{background:#e6f7f0;color:#087052}.path{font-size:19px;font-weight:850;color:var(--navy);margin:10px 0}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px}.metric{border:1px solid var(--line);border-radius:10px;padding:10px}.metric strong{font-size:21px;display:block}.metric small{color:var(--muted)}.reading{padding:11px;margin:12px 0;border-radius:10px;background:#f1f6fb}.dots{display:flex;align-items:end;gap:3px;height:95px;border-bottom:1px solid #9eb4c8;margin:12px 0 5px}.dot{flex:1;min-width:3px;background:#1f70d1;border-radius:3px 3px 0 0}.legend{display:flex;gap:13px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.sw{display:inline-block;width:18px;height:4px;border-radius:3px;margin-right:5px;vertical-align:middle}.business{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:15px 0}.card{padding:17px}.card.good{border-top:5px solid var(--green)}.card.warn{border-top:5px solid var(--amber)}.card.risk{border-top:5px solid var(--red)}.table-wrap{overflow:auto}.table-wrap table{border-collapse:collapse;width:100%;min-width:1050px}.table-wrap th,.table-wrap td{padding:9px;border-bottom:1px solid var(--line);text-align:left;font-size:12px}.table-wrap th{background:#edf4fb;position:sticky;top:0}.num{text-align:right!important;font-variant-numeric:tabular-nums}.method{margin-top:15px;padding:18px}.method details{border-top:1px solid var(--line);padding:10px 0}.method summary{font-weight:800;cursor:pointer}footer{padding:24px;color:var(--muted);font-size:12px;text-align:center}@media(max-width:1050px){.kpis{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.detail{position:static}.business{grid-template-columns:1fr}}@media print{.controls{display:none}.layout{grid-template-columns:1fr}.detail{position:static}body{background:#fff}}
</style></head><body>
<header><span class="tag">RÉSULTAT SIMULÉ · ÉTAT UNIQUE · 30/30</span><h1>Où le réseau résiste — et où il décroche</h1><p>Carte physique interactive des 18 voies fournisseurs testées dans l’état de référence sans dégradation générale ajoutée. Cliquez sur une voie pour lire ses 30 simulations et ses conséquences métier.</p></header>
<main class="wrap"><div class="notice"><strong>Portée :</strong> cette carte décrit un test de résistance simulé. Elle ne mesure ni la performance historique ni la probabilité réelle de défaillance des fournisseurs. La persistance des signaux sera évaluée avec les états 93 et 80.</div>
<section class="kpis"><div class="kpi"><strong>30</strong><span>simulations comparables</span></div><div class="kpi"><strong>18</strong><span>voies physiques testées</span></div><div class="kpi"><strong>1 080</strong><span>incidents simulés</span></div><div class="kpi"><strong>4</strong><span>voies sensibles au retard</span></div><div class="kpi"><strong>18/18</strong><span>voies absorbant la baisse de quantité</span></div></section>
<section class="business"><article class="card risk"><h2>Vulnérabilité forte</h2><p><strong>SDC‑VD0514881A / 016332</strong> dégrade le service dans 24 simulations sur 30. C’est le signal le plus sévère en moyenne.</p></article><article class="card warn"><h2>Effet de seuil</h2><p><strong>SDC‑VD0519670A / 029313</strong> est souvent absorbé, mais peut provoquer une chute supérieure à 40 points. Le réseau résiste puis décroche brutalement.</p></article><article class="card good"><h2>Protection observée</h2><p>La livraison divisée par deux pendant 42 jours est absorbée dans cet état. Cela teste les protections simulées, pas l’absence de risque fournisseur.</p></article></section>
<div class="controls"><label>Incident<select id="mechanism"><option value="transport_delay">Retard de transport de 120 jours</option><option value="planned_delivery_shortfall">Livraison réduite de 50 % pendant 42 jours</option></select></label><label>Produit<select id="product"><option value="all">Tous</option><option>268091</option><option>268967</option></select></label><label>Affichage<select id="sensitivity"><option value="all">Toutes les voies</option><option value="sensitive">Voies avec effet seulement</option></select></label><button id="reset">Réinitialiser la sélection</button></div>
<section class="layout"><div class="panel"><h2>Carte du réseau</h2><p class="sub">La couleur représente la baisse moyenne du service. L’épaisseur représente également la sévérité; une voie grise a été touchée mais absorbée.</p><div class="legend"><span><i class="sw" style="background:#c7d3de"></i>absorbé</span><span><i class="sw" style="background:#ef9f1a"></i>signal modéré</span><span><i class="sw" style="background:#ce3e35"></i>signal fort</span><span><i class="sw" style="background:#7b3fc6"></i>sélection</span></div><div class="map-scroll"><svg id="network" viewBox="0 0 1200 980" aria-label="Réseau fournisseurs vers sites et produits"></svg></div></div><aside class="panel detail" id="detail"></aside></section>
<section class="panel method"><h2>Comparer toutes les voies</h2><p class="sub">Le tableau suit les filtres de la carte. Cliquez sur une ligne pour ouvrir son détail.</p><div class="table-wrap"><table><thead><tr><th>Fournisseur / article</th><th>Chaîne</th><th class="num">Délai planifié</th><th class="num">Baisse moyenne</th><th class="num">Médiane</th><th class="num">P10–P90</th><th class="num">Service dégradé</th><th class="num">Quantités à l’heure perdues</th><th>Lecture métier</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="panel method"><h2>Ce que cette carte permet — et ne permet pas encore</h2><details open><summary>Résultat exploitable maintenant</summary><p>Elle localise les voies qui transmettent un retard fournisseur jusqu’au service du produit fini, quantifie la sévérité moyenne et montre si l’effet est systématique ou dépend d’un seuil.</p></details><details><summary>Pourquoi 30 simulations ?</summary><p>Le même incident est rejoué dans 30 évolutions comparables du réseau. On observe ainsi si la conséquence est stable ou si elle dépend de l’état des stocks, commandes et encours au moment de l’incident.</p></details><details><summary>Limites</summary><p>Les incidents sont imposés, pas observés. Le retard de 120 jours est un test sévère. Aucun levier d’action ni suivi généalogique des lots n’est évalué dans ce paquet. Les états 93 et 80 sont nécessaires avant tout classement final.</p></details></section>
</main><footer>Source : paquet signé op_100 30/30 · signature 0231b89f… · HTML autonome sans ressource externe.</footer>
<script>const DATA=""" + data + """;
const svg=document.getElementById('network'),detail=document.getElementById('detail'),tbody=document.getElementById('rows');let selected=null;
const fmt=(v,d=2)=>Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
function severity(v){return v>=10?'#ce3e35':v>0?'#ef9f1a':'#c7d3de'}
function label(l){return `${l.supplier} · ${l.item}`}
function reading(l){if(l.mean_loss===0)return "Dans cet état, l'incident touche bien une livraison mais les protections simulées évitent une perte de service.";if(l.median_loss===0)return "Effet de seuil : plus de la moitié des situations sont absorbées, mais certains états du réseau provoquent une rupture sévère.";if(l.affected_count>=24)return "Signal récurrent : la majorité des états simulés transmettent l'incident jusqu'au service du produit fini.";return "Signal intermittent : la conséquence dépend fortement des stocks, encours et commandes présents au moment de l'incident."}
function filtered(){const m=document.getElementById('mechanism').value,p=document.getElementById('product').value,s=document.getElementById('sensitivity').value;return DATA.lanes.filter(x=>x.mechanism===m&&(p==='all'||x.product===p)&&(s==='all'||x.mean_loss>0));}
function draw(){const lanes=filtered(),suppliers=[...new Set(lanes.map(x=>x.supplier))].sort();svg.innerHTML='';const NS='http://www.w3.org/2000/svg';const add=(tag,a={})=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(a))e.setAttribute(k,v);svg.appendChild(e);return e};add('text',{x:35,y:28,fill:'#60758b','font-size':13}).textContent='FOURNISSEURS';add('text',{x:565,y:28,fill:'#60758b','font-size':13}).textContent='SITES';add('text',{x:1000,y:28,fill:'#60758b','font-size':13}).textContent='PRODUITS';const sy={};suppliers.forEach((s,i)=>sy[s]=55+i*(885/Math.max(1,suppliers.length-1)));const py={'M-1810':300,'M-1430':680},fy={'268091':300,'268967':680};lanes.slice().sort((a,b)=>a.mean_loss-b.mean_loss).forEach(l=>{const path=add('path',{d:`M 230 ${sy[l.supplier]} C 410 ${sy[l.supplier]},440 ${py[l.plant]},570 ${py[l.plant]}`,stroke:severity(l.mean_loss),'stroke-width':Math.max(2,2+l.mean_loss/3),opacity:l.mean_loss?0.82:0.48,class:'lane'+(selected===l.lane_id?' selected':''),'data-id':l.lane_id});path.onclick=()=>{selected=l.lane_id;show(l);draw()};const p2=add('path',{d:`M 710 ${py[l.plant]} C 850 ${py[l.plant]},900 ${fy[l.product]},990 ${fy[l.product]}`,stroke:'#7aa9d6','stroke-width':4,opacity:.45,fill:'none'});});suppliers.forEach(s=>{const g=add('g',{class:'node'}),r=document.createElementNS(NS,'rect');r.setAttribute('x',35);r.setAttribute('y',sy[s]-17);r.setAttribute('width',195);r.setAttribute('height',34);r.setAttribute('rx',8);g.appendChild(r);const t=document.createElementNS(NS,'text');t.setAttribute('x',47);t.setAttribute('y',sy[s]+4);t.textContent=s;g.appendChild(t);svg.appendChild(g)});Object.entries(py).forEach(([p,y])=>{const g=add('g',{class:'node plant'});g.innerHTML=`<rect x="570" y="${y-35}" width="140" height="70" rx="13"></rect><text x="640" y="${y+5}" text-anchor="middle">${p}</text>`;svg.appendChild(g)});Object.entries(fy).forEach(([p,y])=>{const g=add('g',{class:'node product'});g.innerHTML=`<rect x="990" y="${y-35}" width="170" height="70" rx="13"></rect><text x="1075" y="${y+5}" text-anchor="middle">Produit ${p}</text>`;svg.appendChild(g)});drawTable(lanes);if(!selected&&lanes.length)show(lanes.slice().sort((a,b)=>b.mean_loss-a.mean_loss)[0]);}
function show(l){const max=Math.max(1,...l.samples),bars=l.samples.map(v=>`<i class="dot" title="${fmt(v)} points" style="height:${Math.max(2,90*v/max)}px"></i>`).join('');detail.innerHTML=`<span class="badge sim">SIMULÉ · 30 RÉPÉTITIONS</span> <span class="badge ${l.mean_loss?'high':'abs'}">${l.mean_loss?'SIGNAL À INSTRUIRE':'INCIDENT ABSORBÉ'}</span><div class="path">${esc(l.supplier)} → article ${esc(l.item)} → ${esc(l.plant)} → produit ${esc(l.product)}</div><div class="metrics"><div class="metric"><strong>${fmt(l.mean_loss)}</strong><small>points de service perdus en moyenne</small></div><div class="metric"><strong>${l.affected_count}/30</strong><small>simulations avec service dégradé</small></div><div class="metric"><strong>${fmt(l.median_loss)}</strong><small>médiane</small></div><div class="metric"><strong>${fmt(l.p10)}–${fmt(l.p90)}</strong><small>intervalle P10–P90</small></div><div class="metric"><strong>${fmt(l.late_units_mean,0)}</strong><small>quantités à l'heure perdues, moyenne</small></div><div class="metric"><strong>${fmt(l.production_loss_mean,0)}</strong><small>production non libérée, moyenne</small></div></div><div class="reading"><strong>Lecture métier</strong><br>${reading(l)}</div><h3>Les 30 résultats</h3><div class="dots">${bars}</div><p class="sub">Chaque barre est une simulation; hauteur = baisse du service. Maximum : ${fmt(l.max_loss)} points.</p><div class="reading"><strong>Exposition physique simulée</strong><br>Délai planifié : ${fmt(l.lead_days,0)} jours · volume de référence : ${fmt(l.reference_qty,0)} · ${l.reference_shipment_days} jours d'expédition dans la référence.</div>`}
function drawTable(lanes){tbody.innerHTML=lanes.slice().sort((a,b)=>b.mean_loss-a.mean_loss).map(l=>`<tr data-id="${esc(l.lane_id)}"><td><strong>${esc(l.supplier)}</strong><br>article ${esc(l.item)}</td><td>${esc(l.plant)} → ${esc(l.product)}</td><td class="num">${fmt(l.lead_days,0)} j</td><td class="num"><strong>${fmt(l.mean_loss)}</strong></td><td class="num">${fmt(l.median_loss)}</td><td class="num">${fmt(l.p10)}–${fmt(l.p90)}</td><td class="num">${l.affected_count}/30</td><td class="num">${fmt(l.late_units_mean,0)}</td><td>${reading(l)}</td></tr>`).join('');tbody.querySelectorAll('tr').forEach(tr=>tr.onclick=()=>{const l=lanes.find(x=>x.lane_id===tr.dataset.id);selected=l.lane_id;show(l);draw()})}
['mechanism','product','sensitivity'].forEach(id=>document.getElementById(id).onchange=()=>{selected=null;draw()});document.getElementById('reset').onclick=()=>{selected=null;draw()};draw();
</script></body></html>""")


def build(source_dir: Path, lane_reference: Path, output_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    lane_reference = lane_reference.resolve()
    output_dir = output_dir.resolve(strict=False)
    if output_dir.exists():
        raise DetailedMapError(f"Destination déjà existante : {output_dir}")
    if output_dir == source_dir or output_dir.is_relative_to(source_dir):
        raise DetailedMapError("La nouvelle carte doit rester hors du paquet source.")
    payload = build_payload(source_dir, lane_reference)
    document = render_html(payload)
    output_dir.mkdir(parents=True, exist_ok=False)
    entrypoint = output_dir / ENTRYPOINT
    entrypoint.write_text(_lca_public_map_document(document), encoding="utf-8")
    data_path = output_dir / "donnees_carte_op_100_30_sur_30.json"
    data_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "etudecas.supplier_v8.op100_detailed_network_map.v1.package",
        "status": "complete",
        "source_package_signature": EXPECTED_PACKAGE_SIGNATURE,
        "campaign_signature": EXPECTED_CAMPAIGN_SIGNATURE,
        "engine_runs_started": 0,
        "existing_outputs_modified": False,
        "entrypoint": str(entrypoint),
        "outputs": {
            entrypoint.name: {"sha256": sha256_file(entrypoint), "size_bytes": entrypoint.stat().st_size},
            data_path.name: {"sha256": sha256_file(data_path), "size_bytes": data_path.stat().st_size},
        },
    }
    manifest_path = output_dir / "manifest_carte_detaillee_op_100.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--lane-reference", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build(args.source_dir, args.lane_reference, args.output_dir)
    except (DetailedMapError, OSError, ValueError) as exc:
        print(json.dumps({"status": "refused", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
