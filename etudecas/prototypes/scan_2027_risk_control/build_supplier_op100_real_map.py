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


import hashlib
import base64
import csv
import gzip
import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.lot_trace import build_lot_trace_payload


SOURCE_MAP = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\industrial_supply_preliminary_consolidated_20260904_v4\assets\carte_reseau_existante_hors_ligne.html")
SOURCE_RESULTS = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_checkpoint_30_autonome_20260907T195728Z\bilan_provisoire_op_100_30_sur_30.json")
NOMINAL_NODE_SOURCE = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_network_nominal_trajectory_replay_20260904_v1\maps\carte_run_nominal_actuel.html")
CAUSAL_LOT_SOURCE = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\integrated_risk_lot_maps_20260831_v5\delay_338929_incident_lots_map.html")
CAUSAL_REPLAY_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_all18_causal_lot_replays_20260908_v1")
OP100_GRAPH = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_fixed_triplet_confirmation_plan_20260905_v7\graphs\op100_source.json")
OUTPUT_DIR = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_v8_op100_real_geographic_map_20260908_v1")
OUTPUT_HTML = OUTPUT_DIR / "OUVRIR_VRAIE_CARTE_GEOGRAPHIQUE_OP_100_30_SUR_30.html"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


CHUNK_PATTERN = re.compile(
    r"(?P<a>const DATA_CHUNKED_GZIP_BASE64\s*=\s*)(?P<chunks>\{.*?\})"
    r"(?P<b>;\s*const DATA_CHUNKED_MANIFEST\s*=\s*)(?P<manifest>\{.*?\})(?P<c>;)"
    , re.DOTALL,
)


def _decode_chunks(document: str):
    match = CHUNK_PATTERN.search(document)
    if not match:
        raise RuntimeError("Données autonomes de la carte introuvables.")
    chunks = json.loads(match.group("chunks"))
    manifest = json.loads(match.group("manifest"))
    decoded = {
        key: json.loads(gzip.decompress(base64.b64decode("".join(parts))))
        for key, parts in chunks.items()
    }
    return match, chunks, manifest, decoded


def _decode_legacy_data(document: str) -> dict:
    match = re.search(
        r"const DATA_GZIP_BASE64_CHUNKS\s*=\s*(\[.*?\]);", document, re.DOTALL
    )
    if not match:
        raise RuntimeError("Données de la carte causale introuvables.")
    encoded = "".join(json.loads(match.group(1)))
    return json.loads(gzip.decompress(base64.b64decode(encoded)))


def _namespace_causal_ids(value):
    """Prevent incident lots/campaigns from overwriting nominal identifiers."""
    if isinstance(value, dict):
        return {_namespace_causal_ids(k): _namespace_causal_ids(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_namespace_causal_ids(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?<!INC338929::)(LOT-\d+)", r"INC338929::\1", value)
        value = re.sub(r"(?<!INC338929::)(LEVT-\d+)", r"INC338929::\1", value)
        value = re.sub(
            r"(?<!INC338929::)(CMP-\d+-[A-Za-z0-9:._-]+)",
            r"INC338929::\1",
            value,
        )
    return value


def _namespace_replay_ids(value, namespace: str):
    """Keep independent replay identifiers distinct inside one native lot viewer."""
    if isinstance(value, dict):
        return {
            _namespace_replay_ids(key, namespace): _namespace_replay_ids(item, namespace)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_namespace_replay_ids(item, namespace) for item in value]
    if isinstance(value, str):
        for prefix in ("LOT-", "LEVT-", "CMP-"):
            value = re.sub(
                rf"(?<!{re.escape(namespace)})(?={re.escape(prefix)})",
                namespace,
                value,
            )
    return value


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _existing(path: Path) -> Path | None:
    return path if path.is_file() else None


def _build_representative_replay_traces() -> list[dict]:
    """Build compact causal subgraphs for all 18 representative op_100 lanes."""
    manifest_path = CAUSAL_REPLAY_ROOT / "manifest.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = json.loads(OP100_GRAPH.read_text(encoding="utf-8"))
    scenarios = []
    for target in manifest.get("targets", []):
        output_dir = Path(target["output_dir"])
        data_dir = output_dir / "data"
        registry_dir = output_dir / "risk_lot_registry"
        entities = _read_csv_rows(registry_dir / "risk_impact_entities.csv")
        edges = _read_csv_rows(registry_dir / "risk_impact_edges.csv")
        finished_entities = {
            row["lot_id"]: row
            for row in entities
            if row.get("entity_type") == "finished_product_lot" and row.get("lot_id")
        }
        if not finished_entities:
            continue
        allowed_lot_ids = {
            row.get("lot_id", "") for row in entities if row.get("lot_id")
        }
        allowed_lot_ids.update(
            row.get(key, "")
            for row in edges
            for key in ("source_lot_id", "target_lot_id")
            if row.get(key)
        )
        trace = build_lot_trace_payload(
            data_dir / "production_lot_events.csv",
            data_dir / "production_lot_genealogy.csv",
            data_dir / "production_plan_events.csv",
            raw=raw,
            input_stocks_csv=_existing(data_dir / "production_input_stocks_daily.csv"),
            output_products_csv=_existing(data_dir / "production_output_products_daily.csv"),
            demand_service_csv=_existing(data_dir / "production_demand_service_daily.csv"),
            supplier_stocks_csv=_existing(data_dir / "production_supplier_stocks_daily.csv"),
            visible_finished_product_items=[f"item:{target['target_product_id']}"],
            production_campaigns_csv=data_dir / "production_campaigns.csv",
        )
        allowed_campaign_ids = {
            row.get("entity_id", "")
            for row in entities
            if row.get("entity_type") == "production_campaign" and row.get("entity_id")
        }
        allowed_campaign_ids.update(
            trace.get("lots", {}).get(lot_id, {}).get("production_campaign_id", "")
            for lot_id in finished_entities
        )
        allowed_campaign_ids.discard("")
        deferred_by_campaign = {
            row.get("campaign_id", ""): row for row in trace.get("deferred_orders", [])
        }
        measurement = target.get("measurement_30_of_30", {})
        item_id = str(target["item_id"])
        namespace = f"OP100_{item_id}_{target['seed']}::"
        causal_options = []
        visuals = {}
        for lot_id, entity in finished_entities.items():
            lot = trace.get("lots", {}).get(lot_id)
            if not lot:
                continue
            lot["scenario_kind"] = f"op100_transport_delay_{item_id}"
            lot["scenario_label"] = f"Retard +120 j sur le composant {item_id}"
            option = dict(lot)
            option["label"] = (
                f"[INCIDENT {item_id} — LOT AVAL EXPOSÉ] "
                + str(option.get("label") or lot_id)
            )
            causal_options.append(option)
            campaign_id = str(lot.get("production_campaign_id") or "")
            deferred = deferred_by_campaign.get(campaign_id, {})
            binding_items = {
                str(value).replace("item:", "")
                for value in deferred.get("blocking_input_item_ids", [])
            }
            direct_delay = item_id in binding_items
            exposed_low = float(entity.get("attributed_qty_lower") or 0.0)
            exposed_high = float(entity.get("attributed_qty_upper") or 0.0)
            service_loss = float(
                measurement.get("impact_service_loss_fed_product_pp") or 0.0
            )
            due_loss = float(
                measurement.get("impact_on_due_loss_fed_product_qty") or 0.0
            )
            created_day = int(float(lot.get("created_day") or entity.get("day") or 0))
            stressed_arrival_day = (
                measurement.get("target_latest_stressed_arrival_day")
                or measurement.get("target_arrival_day", "")
            )
            steps = [
                {"kind": "", "eyebrow": "FOURNISSEUR", "title": target["supplier_id"], "caption": "voie testée"},
                {"kind": "alert", "eyebrow": "EXPÉDITION", "title": "+120 jours", "caption": f"décision J{measurement.get('target_decision_day', '')}"},
                {"kind": "alert", "eyebrow": "COMPOSANT", "title": item_id, "caption": f"arrivée retardée J{stressed_arrival_day}"},
                {"kind": "good" if not direct_delay else "alert", "eyebrow": "LOT PRODUIT", "title": lot_id, "caption": f"créé J{created_day}"},
                {"kind": "", "eyebrow": "PRODUIT / CLIENT", "title": target["target_product_id"], "caption": "service aval mesuré"},
            ]
            if direct_delay:
                lot_effect = (
                    f"La campagne de ce lot a aussi enregistré {deferred.get('delay_days', 0)} jour(s) "
                    f"de blocage avec {item_id} comme composant manquant."
                )
            else:
                lot_effect = (
                    "La généalogie prouve que ce lot contient de la matière issue de l’expédition "
                    "touchée. Elle ne suffit pas, à elle seule, à dire que ce lot particulier a été retardé."
                )
            if service_loss <= 1e-9:
                service_effect = (
                    " Dans ce cas représentatif, les protections du réseau absorbent l’incident : "
                    "aucune unité à l’heure n’est perdue."
                )
            else:
                service_effect = (
                    " La comparaison avec la référence utilisant la même graine aléatoire mesure "
                    "la perte de service de toute la réalisation, pas de ce seul lot."
                )
            selection_note = str(target.get("selection_label") or "cas représentatif")
            format_integer = lambda value: f"{value:,.0f}".replace(",", " ")
            visuals[lot_id] = {
                "lot_id": lot_id,
                "short_lot_id": lot_id,
                "scenario_kind": "op100_incident_lineage",
                "badge": f"HYPOTHÈSE SIMULÉE · INCIDENT {item_id} · TRACE NATIVE",
                "headline": f"Comment l’incident {item_id} atteint-il le lot {lot_id} ?",
                "lead": f"Choix parmi 30 répétitions : {selection_note}.",
                "supplier_id": target["supplier_id"],
                "component_id": item_id,
                "factory_id": target["destination_id"],
                "product_id": target["target_product_id"],
                "steps": steps,
                "kpis": [
                    {"value": f"−{service_loss:.2f} pt".replace(".", ","), "label": "service perdu dans cette réalisation"},
                    {"value": format_integer(exposed_low) if abs(exposed_low - exposed_high) < 1e-9 else f"{format_integer(exposed_low)}–{format_integer(exposed_high)}", "label": "unités de ce lot reliées à l’incident"},
                    {"value": f"J{created_day}", "label": "création du lot produit"},
                    {"value": format_integer(due_loss), "label": "unités à l’heure perdues, scénario apparié"},
                ],
                "meaning": (
                    f"{lot_effect}{service_effect}"
                ),
                "proof": (
                    "Chaînage natif par identifiant d’expédition et généalogie physique ; "
                    "couverture de quantité contrôlée à 100 %."
                ),
            }
        causal_options.sort(key=lambda row: (row.get("created_day", 0), row.get("lot_id", "")))
        filtered = {
            **trace,
            "lots": {
                lot_id: lot for lot_id, lot in trace.get("lots", {}).items()
                if lot_id in allowed_lot_ids
            },
            "lot_options": causal_options,
            "events": [
                row for row in trace.get("events", [])
                if row.get("lot_id") in allowed_lot_ids
                or row.get("related_lot_id") in allowed_lot_ids
            ],
            "genealogy": [
                row for row in trace.get("genealogy", [])
                if row.get("parent_lot_id") in allowed_lot_ids
                and row.get("child_lot_id") in allowed_lot_ids
            ],
            "plan_events": [
                row for row in trace.get("plan_events", [])
                if row.get("campaign_id") in allowed_campaign_ids
            ],
            "campaigns": [
                row for row in trace.get("campaigns", [])
                if row.get("campaign_id") in allowed_campaign_ids
            ],
            "deferred_orders": [
                row for row in trace.get("deferred_orders", [])
                if row.get("campaign_id") in allowed_campaign_ids
            ],
            "stock_context": {
                key: value for key, value in trace.get("stock_context", {}).items()
                if key in allowed_lot_ids
            },
        }
        filtered = _namespace_replay_ids(filtered, namespace)
        namespaced_visuals = {}
        for lot_id, visual in visuals.items():
            namespaced_id = namespace + lot_id
            namespaced_visuals[namespaced_id] = visual
            if namespaced_id in filtered["lots"]:
                filtered["lots"][namespaced_id]["causal_visual"] = visual
        scenarios.append({
            "trace": filtered,
            "visuals": namespaced_visuals,
            "scenario": {
                "scenario_id": f"op100_transport_delay_{item_id}_{target['seed']}",
                "label": f"Retard +120 j sur {item_id} — réalisation représentative",
                "supplier_id": target["supplier_id"],
                "destination_id": target["destination_id"],
                "target_product_id": target["target_product_id"],
                "causal_finished_lot_count": len(causal_options),
                "selection_label": target.get("selection_label", ""),
            },
        })
    return scenarios


def _merge_causal_lots(nominal_trace: dict) -> dict:
    causal_data = _decode_legacy_data(CAUSAL_LOT_SOURCE.read_text(encoding="utf-8"))
    causal = _namespace_causal_ids(causal_data["lot_trace"])
    deferred = causal.get("deferred_orders", [])
    impacted_ids = []
    order_by_lot = {}
    for order in deferred:
        impacted_ids.extend(order.get("completed_lot_ids", []))
        for lot_id in order.get("completed_lot_ids", []):
            order_by_lot[lot_id] = order
        if order.get("completed_lot_id"):
            impacted_ids.append(order["completed_lot_id"])
            order_by_lot[order["completed_lot_id"]] = order
    impacted_ids = list(dict.fromkeys(identifier for identifier in impacted_ids if identifier))
    incident_options = []
    for lot_id in impacted_ids:
        lot = causal.get("lots", {}).get(lot_id)
        if not lot:
            continue
        order = order_by_lot[lot_id]
        lot.update({
            "label": (
                "[INCIDENT 338929 — LOT PRODUIT APRÈS REPORT] "
                + lot.get("label", lot_id)
            ),
            "scenario_kind": "incident_338929",
            "scenario_label": "Retard simulé du composant 338929",
            "pf_input_status": "completed_after_input_shortage",
            "pf_input_status_label": (
                f"Libéré après {order.get('delay_days', 0)} jour(s) de report — manque du composant 338929"
            ),
            "pf_availability_status": "completed_after_input_shortage",
            "pf_availability_status_label": (
                f"Production achevée à J{order.get('completed_day', '')} après blocage par 338929"
            ),
            "pf_blocking_input_item_ids": ["item:338929"],
            "pf_input_shortfall_qty": order.get("blocked_lot_qty", 0.0),
            "causal_delay_days": order.get("delay_days", 0),
            "causal_first_delay_day": order.get("first_delay_day", ""),
            "causal_completed_day": order.get("completed_day", ""),
        })
        option = dict(lot)
        option["label"] = (
            "[INCIDENT 338929 — LOT PRODUIT APRÈS REPORT] "
            + option.get("label", lot_id).removeprefix(
                "[INCIDENT 338929 — LOT PRODUIT APRÈS REPORT] "
            ).replace("INC338929::", "")
        )
        incident_options.append(option)
    incident_options.sort(key=lambda row: (row.get("created_day", 0), row.get("lot_id", "")))
    nominal_deferred_options = []
    nominal_deferred_ids = set()
    for order in nominal_trace.get("deferred_orders", []):
        blocking = list(order.get("blocking_input_item_ids", []))
        component = (blocking[0] if blocking else "item:inconnu").replace("item:", "")
        for lot_id in order.get("completed_lot_ids", []) or [order.get("completed_lot_id")]:
            lot = nominal_trace.get("lots", {}).get(lot_id)
            if not lot:
                continue
            nominal_deferred_ids.add(lot_id)
            lot.update({
                "scenario_kind": f"nominal_deferred_{component}",
                "scenario_label": f"Run nominal — report dû au composant {component}",
                "causal_delay_days": order.get("delay_days", 0),
                "causal_first_delay_day": order.get("first_delay_day", ""),
                "causal_completed_day": order.get("completed_day", ""),
            })
            source_option = next(
                (row for row in nominal_trace.get("lot_options", []) if row.get("lot_id") == lot_id),
                lot,
            )
            option = dict(source_option)
            option.update({
                "scenario_kind": f"nominal_deferred_{component}",
                "scenario_label": f"Run nominal — report dû au composant {component}",
                "label": f"[RUN NOMINAL — LOT PRODUIT APRÈS REPORT {component}] " + option.get("label", lot_id),
            })
            nominal_deferred_options.append(option)
    nominal_regular_options = [
        row for row in nominal_trace.get("lot_options", [])
        if row.get("lot_id") not in nominal_deferred_ids
    ]
    merged = dict(nominal_trace)
    merged["lots"] = {**nominal_trace.get("lots", {}), **causal.get("lots", {})}
    # Put the small, decision-relevant incident set first in the existing picker;
    # the nominal catalogue remains complete immediately afterwards.
    merged["lot_options"] = incident_options + nominal_deferred_options + nominal_regular_options
    for key in ("events", "genealogy", "plan_events", "campaigns", "deferred_orders"):
        merged[key] = list(nominal_trace.get(key, [])) + list(causal.get(key, []))
    nominal_stock_context = nominal_trace.get("stock_context", {})
    causal_stock_context = causal.get("stock_context", {})
    if isinstance(nominal_stock_context, dict) and isinstance(causal_stock_context, dict):
        merged["stock_context"] = {**nominal_stock_context, **causal_stock_context}
    else:
        merged["stock_context"] = list(nominal_stock_context or []) + list(causal_stock_context or [])
    merged["causal_scenarios"] = [{
        "scenario_id": "incident_338929",
        "label": "Retard simulé du composant 338929",
        "supplier_id": "SDC-VD0914360C",
        "destination_id": "M-1810",
        "target_product_id": "268091",
        "impacted_released_lot_count": len(incident_options),
        "deferred_order_count": len(deferred),
        "delay_event_count": sum(int(row.get("delay_event_count", 0)) for row in deferred),
    }]
    merged["summary"] = dict(nominal_trace.get("summary", {}))
    merged["summary"].update({
        "causal_scenario_count": 1,
        "causal_impacted_released_lot_count": len(incident_options),
        "causal_deferred_order_count": len(deferred),
    })
    replay_scenarios = _build_representative_replay_traces()
    replay_option_count = 0
    replay_lot_count = 0
    for replay in replay_scenarios:
        trace = replay["trace"]
        replay_options = list(trace.get("lot_options", []))
        replay_option_count += len(replay_options)
        replay_lot_count += len(trace.get("lots", {}))
        merged["lot_options"] = replay_options + list(merged.get("lot_options", []))
        merged["lots"].update(trace.get("lots", {}))
        for key in ("events", "genealogy", "plan_events", "campaigns", "deferred_orders"):
            merged[key] = list(merged.get(key, [])) + list(trace.get(key, []))
        existing_stock_context = merged.get("stock_context", [])
        replay_stock_context = trace.get("stock_context", [])
        if isinstance(existing_stock_context, dict) and isinstance(replay_stock_context, dict):
            existing_stock_context.update(replay_stock_context)
        elif isinstance(existing_stock_context, list) and isinstance(replay_stock_context, list):
            existing_stock_context.extend(replay_stock_context)
        elif replay_stock_context:
            # Preserve both schemas without silently dropping either source.
            merged["stock_context"] = {
                "nominal": existing_stock_context,
                "representative_replays": replay_stock_context,
            }
        merged["causal_scenarios"].append(replay["scenario"])
    merged["summary"].update({
        "causal_scenario_count": 1 + len(replay_scenarios),
        "op100_representative_causal_finished_lot_count": replay_option_count,
        "op100_representative_causal_subgraph_lot_count": replay_lot_count,
    })
    return merged


def _causal_lot_visual_payload(document: str) -> dict:
    _, _, _, decoded = _decode_chunks(document)
    trace = decoded["lot_trace"]
    lots = trace.get("lots", {})
    payload = {
        lot_id: dict(lot["causal_visual"])
        for lot_id, lot in lots.items()
        if isinstance(lot, dict) and isinstance(lot.get("causal_visual"), dict)
    }
    for order in trace.get("deferred_orders", []):
        is_incident = "INC338929::" in str(order.get("campaign_id", ""))
        blocking_items = list(order.get("blocking_input_item_ids", []))
        component_id = (
            str(blocking_items[0]).replace("item:", "") if blocking_items else "inconnu"
        )
        supplier_id = {
            "338929": "SDC-VD0914360C",
            "344135": "SDC-VD0993480A",
        }.get(component_id, "Fournisseur associé")
        for lot_id in order.get("completed_lot_ids", []) or [order.get("completed_lot_id")]:
            if not lot_id or lot_id not in lots:
                continue
            # A native risk-to-lot card carries stronger and more complete
            # causality than the generic deferred-order summary.
            if lot_id in payload:
                continue
            lot = lots[lot_id]
            payload[lot_id] = {
                "lot_id": lot_id,
                "short_lot_id": lot_id.replace("INC338929::", ""),
                "scenario_kind": "incident" if is_incident else "nominal",
                "badge": (
                    f"HYPOTHÈSE SIMULÉE · INCIDENT {component_id}"
                    if is_incident else f"SIMULÉ · REPORT DANS LE RUN NOMINAL · {component_id}"
                ),
                "supplier_id": supplier_id,
                "component_id": component_id,
                "factory_id": order.get("node_id", "M-1810"),
                "product_id": str(order.get("output_item_id", "item:268091")).replace("item:", ""),
                "first_delay_day": order.get("first_delay_day"),
                "last_delay_day": order.get("last_delay_day"),
                "completed_day": order.get("completed_day"),
                "delay_days": order.get("delay_days", 0),
                "blocked_qty": order.get("blocked_lot_qty", 0.0),
                "released_qty": order.get("actual_completion_qty", lot.get("qty", 0.0)),
                "upstream_lot_count": lot.get("upstream_lot_count", 0),
                "downstream_lot_count": lot.get("downstream_lot_count", 0),
                "downstream_node_count": lot.get("downstream_node_count", 0),
                "event_count": lot.get("event_count", 0),
                "meaning": (
                    f"L’incident imposé sur {component_id} a décalé la fabrication. Le lot a ensuite été terminé et libéré : il s’agit d’une indisponibilité temporaire, pas d’une perte définitive."
                    if is_incident else
                    f"Sans incident ajouté, le besoin en {component_id} a déjà retardé cette fabrication dans le run nominal. Ce signal révèle une fragilité interne de la configuration simulée."
                ),
            }
    return payload


def _with_original_node_curves(current_document: str) -> str:
    """Restore the audited nominal node panels removed by the compact delivery."""
    current_match, chunks, manifest, current = _decode_chunks(current_document)
    _, _, _, nominal = _decode_chunks(NOMINAL_NODE_SOURCE.read_text(encoding="utf-8"))
    replace_keys = (
        "timeline_horizon_days", "factory_hover_series", "factory_hover_images",
        "factory_current_metrics", "supplier_hover_images",
        "distribution_center_hover_images", "customer_hover_images",
        "customer_current_metrics", "global_kpi_tree", "lot_trace",
        "material_balance_rows", "supplier_local_metrics", "simulation_diagnostics",
    )
    for key in replace_keys:
        if key in nominal:
            current[key] = nominal[key]
    current["lot_trace"] = _merge_causal_lots(current["lot_trace"])
    # Restore the rich nominal figures on nodes/edges while preserving the newer
    # campaign-level state and uncertainty payloads from the consolidated map.
    old_model = nominal.get("model_panel", {})
    new_model = current.get("model_panel", {})
    for section in ("nodes", "edges"):
        merged = dict(new_model.get(section, {}))
        for identifier, assets in old_model.get(section, {}).items():
            merged[identifier] = {**merged.get(identifier, {}), **assets}
        new_model[section] = merged
    current["model_panel"] = new_model
    for key in replace_keys + ("model_panel",):
        raw = json.dumps(current[key], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        compressed = gzip.compress(raw, mtime=0)
        encoded = base64.b64encode(compressed).decode("ascii")
        chunks[key] = [encoded[i:i + 262144] for i in range(0, len(encoded), 262144)]
        manifest[key]["raw_bytes"] = len(raw)
        manifest[key]["compressed_bytes"] = len(compressed)
    replacement = (
        current_match.group("a") + json.dumps(chunks, separators=(",", ":"))
        + current_match.group("b") + json.dumps(manifest, separators=(",", ":"))
        + current_match.group("c")
    )
    return current_document[:current_match.start()] + replacement + current_document[current_match.end():]


def build() -> Path:
    source_hash = sha256(SOURCE_MAP)
    replay_manifest = json.loads(
        (CAUSAL_REPLAY_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    document = _with_original_node_curves(SOURCE_MAP.read_text(encoding="utf-8"))
    document = document.replace(
        "Les cascades actuelles et le suivi causal des lots ne sont pas encore intégrés à la carte ; utiliser aussi les trois vues du bilan.",
        "Les 18 voies fournisseurs ont été retracées : 12 atteignent des lots finis dans le cas représentatif et 6 n’en atteignent aucun avant la fin de l’horizon. Les lots trouvés sont intégrés au sélecteur existant.",
    )
    causal_visuals = _causal_lot_visual_payload(document)
    causal_visual_payload = json.dumps(
        causal_visuals, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    results = json.loads(SOURCE_RESULTS.read_text(encoding="utf-8"))
    rows = results["lane_statistics"]
    rows.sort(key=lambda r: (r["mechanism"], -float(r["service_loss_mean_pp"]), r["supplier_id"], r["item_id"]))
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    css = r"""
<style id="op100RealMapStyle">
#op100Open{position:fixed;right:18px;bottom:18px;z-index:99990;border:0;border-radius:999px;background:#0b3b75;color:#fff;padding:13px 19px;font:700 14px system-ui;box-shadow:0 8px 28px #0f172a55;cursor:pointer}
#op100Panel{position:fixed;z-index:99991;right:14px;top:76px;bottom:14px;width:min(550px,calc(100vw - 28px));background:#f8fafc;border:1px solid #cbd5e1;border-radius:18px;box-shadow:0 18px 55px #0f172a66;display:none;overflow:hidden;font:14px/1.38 system-ui;color:#0f2747}
#op100Panel.open{display:flex;flex-direction:column}.op100Head{padding:16px 18px;background:#0b3b75;color:white}.op100Head h2{font-size:19px;margin:2px 36px 4px 0}.op100Head p{margin:0;color:#dbeafe;font-size:12px}.op100Close{position:absolute;right:15px;top:13px;border:0;background:#ffffff22;color:white;border-radius:50%;width:32px;height:32px;font-size:21px;cursor:pointer}.op100Kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:10px 12px}.op100Kpi{background:white;border:1px solid #dbe5f0;border-radius:10px;padding:8px}.op100Kpi strong{display:block;font-size:18px}.op100Kpi span{font-size:11px;color:#52657b}.op100Controls{display:flex;gap:8px;padding:0 12px 10px}.op100Controls select{flex:1;padding:8px;border:1px solid #b8c6d8;border-radius:8px;background:white}.op100Note{margin:0 12px 10px;padding:9px 10px;border-radius:9px;background:#fff7ed;border-left:4px solid #ea580c;font-size:12px}.op100Rows{overflow:auto;padding:0 12px 14px}.op100Row{background:white;border:1px solid #dbe5f0;border-radius:11px;padding:10px;margin-bottom:8px;cursor:pointer}.op100Row:hover,.op100Row.active{border-color:#2563eb;box-shadow:0 0 0 2px #dbeafe}.op100Title{display:flex;justify-content:space-between;gap:8px;font-weight:800}.op100Loss{color:#b42318}.op100Path{font-size:12px;color:#52657b;margin:3px 0 7px}.op100Metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;font-size:11px}.op100Metrics b{display:block;font-size:13px;color:#102a4c}.op100Zero{color:#64748b}.op100Detail{display:none;margin-top:9px;padding-top:8px;border-top:1px solid #e2e8f0;font-size:12px}.op100Row.active .op100Detail{display:block}@media(max-width:700px){#op100Panel{left:8px;right:8px;top:76px;bottom:8px;width:auto}}
.causalLotVisual{border:2px solid #fb923c;border-radius:14px;background:linear-gradient(135deg,#fff7ed,#fff);padding:14px;margin:0 0 14px;color:#172033;box-shadow:0 6px 18px #9a341222}.causalLotVisualHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.causalLotBadge{display:inline-block;border-radius:999px;background:#ffedd5;color:#9a3412;padding:4px 9px;font-size:10px;font-weight:900;letter-spacing:.04em}.causalLotVisual h3{font-size:17px;margin:6px 0 3px}.causalLotVisualLead{font-size:12px;color:#5b6472}.causalLotKpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:12px 0}.causalLotKpi{border:1px solid #fed7aa;border-radius:10px;background:#fff;padding:8px}.causalLotKpi strong{display:block;font-size:18px;color:#9a3412}.causalLotKpi span{font-size:10px;color:#657083}.causalLotFlow{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));align-items:stretch;gap:5px;margin:12px 0}.causalLotStep{grid-column:span 1;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:8px 5px;text-align:center;font-size:10px}.causalLotStep b{display:block;font-size:11px;margin:3px 0}.causalLotStep.alert{border-color:#ef4444;background:#fff1f2}.causalLotStep.good{border-color:#22c55e;background:#f0fdf4}.causalLotArrow{display:flex;align-items:center;justify-content:center;color:#ea580c;font-size:20px;font-weight:900}.causalLotMeaning{border-left:4px solid #2563eb;background:#eff6ff;border-radius:8px;padding:9px 10px;font-size:12px}.causalLotProof{font-size:10px;color:#657083;margin-top:8px}@media(max-width:850px){.causalLotKpis{grid-template-columns:repeat(2,1fr)}.causalLotFlow{display:flex;overflow:auto}.causalLotStep{min-width:135px}.causalLotArrow{min-width:20px}}
#lotTracePanel.causalVisualActive{z-index:60;width:min(1080px,calc(100vw - 32px));max-height:min(700px,calc(100vh - 280px))}
.op100LotBtn{margin-top:9px;border:0;border-radius:8px;background:#0f766e;color:#fff;padding:7px 10px;font-weight:800;cursor:pointer}.op100LotBtn:hover{background:#115e59}
.op100NoLot{margin-top:9px;border-radius:8px;background:#f1f5f9;border:1px solid #cbd5e1;color:#475569;padding:7px 9px;font-weight:700}
</style>"""
    body = r"""
<button id="op100Open" type="button">Résultats op_100 · 30/30</button>
<aside id="op100Panel" aria-label="Résultats simulés op 100">
 <div class="op100Head"><button class="op100Close" id="op100Close" aria-label="Fermer">×</button><h2>État simulé proche de 100 %</h2><p>Carte géographique réelle + résultats conditionnels de 30 répétitions</p></div>
 <div class="op100Kpis"><div class="op100Kpi"><strong>30/30</strong><span>répétitions</span></div><div class="op100Kpi"><strong>18</strong><span>voies physiques</span></div><div class="op100Kpi"><strong>1 080</strong><span>incidents appariés</span></div></div>
 <div class="op100Controls"><select id="op100Mechanism"><option value="transport_delay">Retard transport +120 jours</option><option value="planned_delivery_shortfall">Livraison réduite de 50 % pendant 42 jours</option></select><select id="op100Site"><option value="">Tous les sites</option><option>M-1810</option><option>M-1430</option></select></div>
 <p class="op100Note" id="op100Note"></p><div class="op100Rows" id="op100Rows"></div>
</aside>
<script id="op100RealMapScript">
const OP100_ROWS=__PAYLOAD__;
const CAUSAL_LOT_VISUALS=__CAUSAL_VISUAL_PAYLOAD__;
(()=>{const panel=document.getElementById('op100Panel'),box=document.getElementById('op100Rows'),mech=document.getElementById('op100Mechanism'),site=document.getElementById('op100Site'),note=document.getElementById('op100Note');
const nf=new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}),ff=v=>Number(v).toFixed(2).replace('.',',');
function render(){let rows=OP100_ROWS.filter(r=>r.mechanism===mech.value&&(!site.value||r.dst_node_id===site.value));rows.sort((a,b)=>b.service_loss_mean_pp-a.service_loss_mean_pp);note.textContent=mech.value==='transport_delay'?'Stress-test sévère : un retard de 120 jours est imposé. Les premières lignes indiquent où les protections actuelles cèdent le plus souvent.':'À cet état de fonctionnement, ce stress a bien touché les 18 voies mais les stocks et flux déjà engagés en absorbent l’effet sur le service. Cela ne signifie pas que les fournisseurs sont sans risque.';box.innerHTML=rows.map((r,i)=>{const item=String(r.item_id).replace('item:','');const hasLots=Object.values(CAUSAL_LOT_VISUALS).some(d=>d.scenario_kind==='op100_incident_lineage'&&d.supplier_id===r.supplier_id&&d.component_id===item);const lotAction=mech.value!=='transport_delay'?'':hasLots?`<br><button class="op100LotBtn" data-supplier="${r.supplier_id}" data-item="${item}">Voir les lots causalement exposés</button>`:'<div class="op100NoLot">Traçage réalisé : aucun lot produit aval atteint avant la fin de l’horizon dans le cas représentatif.</div>';return `<article class="op100Row" tabindex="0"><div class="op100Title"><span>${i+1}. ${r.supplier_id}</span><span class="${r.service_loss_mean_pp?'op100Loss':'op100Zero'}">−${ff(r.service_loss_mean_pp)} pt</span></div><div class="op100Path">Article ${item} → ${r.dst_node_id} → produit ${r.target_product_id}</div><div class="op100Metrics"><span><b>${r.positive_service_effect_count}/30</b>répétitions pénalisées</span><span><b>${ff(r.service_loss_p10_pp)}–${ff(r.service_loss_p90_pp)}</b>dispersion P10–P90</span><span><b>${nf.format(r.on_due_units_lost_mean)}</b>unités à l’heure perdues</span></div><div class="op100Detail"><b>Lecture métier.</b> Baisse médiane : ${ff(r.service_loss_median_pp)} point(s) ; maximum : ${ff(r.service_loss_max_pp)}. Production non libérée : ${nf.format(r.production_not_released_mean_qty)} unités en moyenne. Incident effectivement rencontré : ${r.physical_exercise_count}/30. Résultat simulé pour ce seul état, pas une notation historique du fournisseur.${lotAction}</div></article>`}).join('');box.querySelectorAll('.op100Row').forEach(el=>{const toggle=()=>{box.querySelectorAll('.op100Row').forEach(x=>x!==el&&x.classList.remove('active'));el.classList.toggle('active')};el.onclick=toggle;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle()}}});box.querySelectorAll('.op100LotBtn').forEach(btn=>btn.onclick=e=>{e.stopPropagation();openCausalLot(btn.dataset.supplier,btn.dataset.item)});}
document.getElementById('op100Open').onclick=()=>panel.classList.add('open');document.getElementById('op100Close').onclick=()=>panel.classList.remove('open');
const qty=v=>new Intl.NumberFormat('fr-FR',{maximumFractionDigits:0}).format(Number(v||0));
function causalCard(d){const k=d.kpis||[{value:`${d.delay_days} j`,label:'de report de production'},{value:qty(d.blocked_qty),label:'unités temporairement bloquées'},{value:`J${d.completed_day}`,label:'jour de libération du lot'},{value:qty(d.released_qty),label:'unités finalement libérées'}];const s=d.steps||[{kind:'',eyebrow:'FOURNISSEUR',title:d.supplier_id,caption:'flux amont'},{kind:'alert',eyebrow:'COMPOSANT',title:d.component_id,caption:'manquant'},{kind:'alert',eyebrow:'PRODUCTION',title:d.factory_id,caption:`report J${d.first_delay_day}–J${d.last_delay_day}`},{kind:'good',eyebrow:'LOT LIBÉRÉ',title:d.short_lot_id,caption:`à J${d.completed_day}`},{kind:'',eyebrow:'PRODUIT',title:d.product_id,caption:`${d.downstream_lot_count} lot(s) aval`}];const flow=s.map((x,i)=>`${i?'<div class="causalLotArrow">→</div>':''}<div class="causalLotStep ${x.kind||''}"><span>${x.eyebrow}</span><b>${x.title}</b><small>${x.caption}</small></div>`).join('');return `<section class="causalLotVisual"><div class="causalLotVisualHead"><div><span class="causalLotBadge">${d.badge}</span><h3>${d.headline||`Pourquoi le lot ${d.short_lot_id} a-t-il été retardé ?`}</h3><div class="causalLotVisualLead">${d.lead||'Lecture directe de la cause jusqu’à la remise à disposition du produit.'}</div></div></div><div class="causalLotKpis">${k.map(x=>`<div class="causalLotKpi"><strong>${x.value}</strong><span>${x.label}</span></div>`).join('')}</div><div class="causalLotFlow">${flow}</div><div class="causalLotMeaning"><b>Ce que cela signifie :</b> ${d.meaning}</div><div class="causalLotProof">${d.proof||`Preuve détaillée sous cette synthèse : ${d.upstream_lot_count} lots amont, ${d.downstream_lot_count} lots aval et événements de production associés.`}</div></section>`}
function selectedCausal(selectId){const el=document.getElementById(selectId);return el?CAUSAL_LOT_VISUALS[el.value]:null}
function cleanCausalNamespace(root){if(!root)return;const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode())node.nodeValue=node.nodeValue.replaceAll('INC338929::','').replace(/OP100_[A-Za-z0-9_]+::/g,'')}
function openCausalLot(supplier,item){const match=Object.entries(CAUSAL_LOT_VISUALS).find(([,d])=>d.supplier_id===supplier&&d.component_id===item&&d.scenario_kind==='op100_incident_lineage');if(!match)return;const select=document.getElementById('lotTraceSelect');if(select){select.value=match[0];select.dispatchEvent(new Event('change',{bubbles:true}))}panel.classList.remove('open');setTimeout(()=>document.getElementById('lotTraceFocusBtn')?.click(),40)}
function renderCausalVisuals(){const panelBody=document.getElementById('lotTracePanelBody'),lotPanel=document.getElementById('lotTracePanel'),panelData=selectedCausal('lotTraceSelect');lotPanel?.classList.toggle('causalVisualActive',!!panelData);if(panelData)document.getElementById('factoryHoverPanel')?.classList.remove('visible');if(panelBody&&!panelBody.querySelector('.causalLotVisual')&&panelData)panelBody.insertAdjacentHTML('afterbegin',causalCard(panelData));if(panelData){cleanCausalNamespace(document.getElementById('lotTracePanelTitle'));cleanCausalNamespace(panelBody);cleanCausalNamespace(document.getElementById('stats'))}const graph=document.getElementById('lotTraceGraphWrap');if(graph){document.getElementById('causalLotVisualModal')?.remove();const d=selectedCausal('lotTraceModalSelect');if(d){const holder=document.createElement('div');holder.id='causalLotVisualModal';holder.innerHTML=causalCard(d);graph.parentNode.insertBefore(holder,graph);setTimeout(()=>cleanCausalNamespace(document.getElementById('lotTraceModal')),0)}}}
const lotPanelBody=document.getElementById('lotTracePanelBody'),lotGraph=document.getElementById('lotTraceGraphWrap');if(lotPanelBody)new MutationObserver(()=>setTimeout(renderCausalVisuals,0)).observe(lotPanelBody,{childList:true});if(lotGraph)new MutationObserver(()=>setTimeout(renderCausalVisuals,0)).observe(lotGraph,{childList:true});['lotTraceSelect','lotTraceModalSelect'].forEach(id=>document.getElementById(id)?.addEventListener('change',()=>setTimeout(renderCausalVisuals,30)));['lotTraceFocusBtn','lotTraceOpenBtn'].forEach(id=>document.getElementById(id)?.addEventListener('click',()=>setTimeout(renderCausalVisuals,60)));
mech.onchange=render;site.onchange=render;render();})();
</script>""".replace("__PAYLOAD__", payload).replace("__CAUSAL_VISUAL_PAYLOAD__", causal_visual_payload)
    marker = "</body>"
    if marker not in document or "Plotly.newPlot" not in document:
        raise RuntimeError("La carte source n'a pas le contrat attendu.")
    enriched = document.replace(marker, css + body + "\n" + marker, 1)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(_lca_public_map_document(enriched), encoding="utf-8")
    manifest = {
        "schema_version": "etudecas.supplier_v8.op100_real_geographic_map.v1",
        "entrypoint": OUTPUT_HTML.name,
        "fully_offline": True,
        "simulation_started": False,
        "source_map": str(SOURCE_MAP),
        "source_map_sha256": source_hash,
        "source_results": str(SOURCE_RESULTS),
        "source_results_sha256": sha256(SOURCE_RESULTS),
        "source_package_signature": "0231b89f05b07d739fafac72478926bfb23d6cfd2edf8f659b786cdaa8d1367a",
        "nominal_node_curve_source": str(NOMINAL_NODE_SOURCE),
        "nominal_node_curve_source_sha256": sha256(NOMINAL_NODE_SOURCE),
        "causal_lot_source": str(CAUSAL_LOT_SOURCE),
        "causal_lot_source_sha256": sha256(CAUSAL_LOT_SOURCE),
        "causal_lot_scope": "338929_detaille_plus_18_voies_op100_representatives_et_reports_nominaux",
        "causal_replay_root": str(CAUSAL_REPLAY_ROOT),
        "causal_replay_manifest_sha256": sha256(CAUSAL_REPLAY_ROOT / "manifest.json"),
        "representative_item_count": len({
            row.get("component_id") for row in causal_visuals.values()
            if row.get("scenario_kind") == "op100_incident_lineage"
        }),
        "representative_replayed_lane_count": int(replay_manifest.get("lane_count", 0)),
        "representative_lane_without_finished_lot_count": int(replay_manifest.get("lane_count", 0)) - len({
            row.get("component_id") for row in causal_visuals.values()
            if row.get("scenario_kind") == "op100_incident_lineage"
        }),
        "representative_causal_finished_lot_count": sum(
            row.get("scenario_kind") == "op100_incident_lineage"
            for row in causal_visuals.values()
        ),
        "causal_visual_card_count": len(causal_visuals),
        "lane_count": 18,
        "incident_case_count": 1080,
        "simulation_count": 30,
    }
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if sha256(SOURCE_MAP) != source_hash:
        raise RuntimeError("La carte source a été modifiée.")
    return OUTPUT_HTML


if __name__ == "__main__":
    print(build())
