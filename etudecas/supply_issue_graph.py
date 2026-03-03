"""Plot full supply knowledge graph and annotate issue hotspots."""

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


from dataclasses import dataclass
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

from supply_graph_tools import _canonical_coord_keys, _extract_code, _infer_role


@dataclass
class ActorInfo:
    actor_id: str
    role: str
    description: str
    lat: float
    lon: float


@dataclass
class SupplyEdgeInfo:
    source: str
    target: str
    product: str
    relation: str
    zone: str
    risk_score: float
    risk_display: float
    material_family: str


@dataclass
class DataPocInfo:
    relation_by_triplet: dict[tuple[str, str, str], dict[str, float | str]]
    product_bom_criticality: dict[str, float]
    matched_relations: int = 0
    unmatched_relations: int = 0


def _safe_float(value: object, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


# Historical route distances (km), without geographic positions.
_PUBLISHED_ROUTE_KM = {
    ('Actor:DC - 1910', 'Actor:C - XXXXX'): 605.193859957,
    ('Manufacturer of Cosmetics - D1810', 'Actor:DC - D1910'): 144.476803328,
    ('Manufacturer of Drugs - D1430', 'Actor:DC - D1910'): 481.18352932,
    ('Supplier of Packaging - VD0508918A', 'Manufacturer of Drugs - D1430'): 156.03463156,
    ('Supplier of Packaging - VD0520115A', 'Manufacturer of Drugs - D1430'): 488.184263708,
    ('Supplier of Packaging - VD0525412A', 'Manufacturer of Drugs - D1430'): 288.344370929,
    ('Supplier of Packaging - VD0901566A', 'Manufacturer of Cosmetics - D1810'): 608.775992029,
    ('Supplier of Packaging - VD0914360C', 'Manufacturer of Cosmetics - D1810'): 301.302630798,
    ('Supplier of Packaging - VD0989480A', 'Manufacturer of Cosmetics - D1810'): 304.416997606,
    ('Supplier of Packaging - VD0993480A', 'Manufacturer of Drugs - D1430'): 268.176072898,
    ('Supplier of Packaging - VD1095770A', 'Manufacturer of Drugs - D1430'): 234.390823392,
    ('Supplier of Raw Materials - D1450', 'Manufacturer of Cosmetics - D1810'): 97.8126964633,
    ('Supplier of Raw Materials - D1450', 'Manufacturer of Drugs - D1430'): 426.177899471,
    ('Supplier of Raw Materials - VD0500655A', 'Manufacturer of Cosmetics - D1810'): 928.848074604,
    ('Supplier of Raw Materials - VD0505677A', 'Manufacturer of Cosmetics - D1810'): 756.554654049,
    ('Supplier of Raw Materials - VD0514881A', 'Manufacturer of Cosmetics - D1810'): 1668.7261281,
    ('Supplier of Raw Materials - VD0518684A', 'Manufacturer of Cosmetics - D1810'): 1199.85649578,
    ('Supplier of Raw Materials - VD0519670A', 'Manufacturer of Cosmetics - D1810'): 113.419082337,
    ('Supplier of Raw Materials - VD0520132A', 'Manufacturer of Cosmetics - D1810'): 592.119705011,
    ('Supplier of Raw Materials - VD0520132A', 'Manufacturer of Drugs - D1430'): 154.200260737,
    ('Supplier of Raw Materials - VD0910216A', 'Manufacturer of Cosmetics - D1810'): 261.265280532,
    ('Supplier of Raw Materials - VD0914320A', 'Manufacturer of Cosmetics - D1810'): 203.90297886,
    ('Supplier of Raw Materials - VD0914690A', 'Manufacturer of Drugs - D1430'): 395.477595016,
    ('Supplier of Raw Materials - VD0951020A', 'Manufacturer of Cosmetics - D1810'): 570.044834709,
    ('Supplier of Raw Materials - VD0964290A', 'Manufacturer of Cosmetics - D1810'): 568.505246198,
    ('Supplier of Raw Materials - VD0990780A', 'Manufacturer of Cosmetics - D1810'): 503.470473161,
    ('Supplier of Raw Materials - VD1091642A', 'Manufacturer of Cosmetics - D1810'): 629.662277867,
    ('Supplier of Raw Materials - VD1096202A', 'Manufacturer of Cosmetics - D1810'): 568.505246198,
}

def _stored_route_km(source, target):
    return _PUBLISHED_ROUTE_KM.get((source, target))

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius_km * math.asin(math.sqrt(a))


def _material_family(description: str) -> str:
    d = (description or "").lower()
    if "raw material" in d:
        return "raw_material"
    if "packaging" in d:
        return "packaging"
    if "manufacturer" in d or "drugs" in d or "cosmetics" in d:
        return "finished_or_intermediate"
    return "other"


def _normalize_product(product: str) -> str:
    value = (product or "").replace("P:", "").strip()
    return value if value else "unknown"


def _normalize_product_code(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    text = text.replace("P:", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _actor_sheet_keys(actor_id: str, role: str) -> list[str]:
    code = _extract_code(actor_id)
    if not code:
        return []
    prefix = {
        "Supplier Distribution Center": "SDC",
        "Manufacturer": "M",
        "Distribution Center": "DC",
        "Customer": "C",
    }.get(role, "")
    keys = []
    if prefix:
        keys.append(f"{prefix} - {code}")
        if prefix in ("DC", "M", "C") and code.startswith("D"):
            keys.append(f"{prefix} - {code[1:]}")
        if prefix == "DC" and code.isdigit():
            keys.append(f"{prefix} - D{code}")
    return list(dict.fromkeys(keys))


def _load_data_poc(data_poc_path: str | Path | None) -> DataPocInfo | None:
    if data_poc_path is None:
        return None
    path = Path(data_poc_path)
    if not path.exists():
        return None

    relation_by_triplet: dict[tuple[str, str, str], dict[str, float | str]] = {}
    product_bom_criticality: dict[str, float] = {}

    try:
        relations = pd.read_excel(path, sheet_name="Relations_acteurs")
        bom = pd.read_excel(path, sheet_name="BOM")
    except Exception:
        return None

    for _, row in relations.iterrows():
        supplier = str(row.get("supplier", "")).strip()
        customer = str(row.get("customer", "")).strip()
        product = _normalize_product_code(row.get("product", ""))
        if not supplier or not customer or product == "unknown":
            continue
        relation_by_triplet[(supplier, customer, product)] = {
            "sell_price": _safe_float(row.get("sell_price"), default=float("nan")),
            "price_base": _safe_float(row.get("price_base"), default=float("nan")),
            "quantity_unit": str(row.get("quantity_unit", "")).strip(),
            "supply_order_frequency": _safe_float(row.get("supply_order_frequency"), default=float("nan")),
            "customer_priority_rank": _safe_float(row.get("customer_priority_rank"), default=float("nan")),
            "supplier_priority_rank": _safe_float(row.get("supplier_priority_rank"), default=float("nan")),
            "delay_step_limit": _safe_float(row.get("delay_step_limit"), default=float("nan")),
            "transport_cost": _safe_float(row.get("transport_cost"), default=float("nan")),
        }

    bom_valid = bom[(bom.get("output_product").notna()) & (bom.get("input_product").notna())].copy()
    if not bom_valid.empty:
        bom_valid["output_product_norm"] = bom_valid["output_product"].apply(_normalize_product_code)
        bom_valid["input_product_norm"] = bom_valid["input_product"].apply(_normalize_product_code)
        bom_valid["quantity_num"] = bom_valid["quantity"].apply(lambda x: max(0.0, _safe_float(x, default=0.0)))
        totals_by_output = bom_valid.groupby("output_product_norm")["quantity_num"].sum().to_dict()
        raw_score: dict[str, float] = defaultdict(float)
        for _, row in bom_valid.iterrows():
            output_product = row["output_product_norm"]
            input_product = row["input_product_norm"]
            total = totals_by_output.get(output_product, 0.0)
            if total <= 1e-12:
                continue
            raw_score[input_product] += float(row["quantity_num"]) / total
        if raw_score:
            max_score = max(raw_score.values())
            if max_score > 1e-12:
                product_bom_criticality = {k: float(v / max_score) for k, v in raw_score.items()}

    return DataPocInfo(
        relation_by_triplet=relation_by_triplet,
        product_bom_criticality=product_bom_criticality,
        matched_relations=0,
        unmatched_relations=len(relation_by_triplet),
    )


def _stage_zone_from_backlog_key(backlog_key: str) -> str:
    key = backlog_key.replace("backlog_", "")
    if "distribution_to_stock_arrivee_ligne_production" in key:
        return "distribution_to_customer"
    if "stock_distribution_to_distribution" in key:
        return "manufacturer_to_distribution"
    if "stock_amont_to_stock_apres_transport_amont" in key:
        return "supplier_to_manufacturer"
    if "stock_apres_transport_amont_to_transformation_1" in key:
        return "supplier_to_manufacturer"
    if "transformation_1" in key or "transformation_2" in key or "stock_apres_transport_t1_to_transformation_2" in key:
        return "manufacturing_internal"
    return "other"


def _role_flow_zone(source_role: str, target_role: str) -> str:
    if source_role == "Supplier Distribution Center" and target_role == "Manufacturer":
        return "supplier_to_manufacturer"
    if source_role == "Manufacturer" and target_role == "Distribution Center":
        return "manufacturer_to_distribution"
    if source_role == "Distribution Center" and target_role == "Customer":
        return "distribution_to_customer"
    return "other"


def _fallback_positions(actor_ids: list[str], actor_roles: dict[str, str]) -> dict[str, tuple[float, float]]:
    by_role: dict[str, list[str]] = {}
    for actor_id in actor_ids:
        by_role.setdefault(actor_roles[actor_id], []).append(actor_id)

    role_order = [
        "Supplier Distribution Center",
        "Manufacturer",
        "Distribution Center",
        "Customer",
        "Unknown",
    ]
    role_x = {role: float(i) for i, role in enumerate(role_order)}

    output: dict[str, tuple[float, float]] = {}
    for role, ids in by_role.items():
        ids_sorted = sorted(ids)
        x = role_x.get(role, float(len(role_order)))
        for idx, actor_id in enumerate(ids_sorted):
            y = float(idx) - 0.5 * max(0, len(ids_sorted) - 1)
            output[actor_id] = (x, y)
    return output


def _build_actor_info(graph: dict, coords: dict[str, list[float]]) -> dict[str, ActorInfo]:
    actor_nodes = [n for n in graph.get("nodes", []) if n.get("layer") in ("actor", "actor_placeholder")]
    actor_ids = [n["id"] for n in actor_nodes]
    actor_roles = {n["id"]: _infer_role(n["id"], n.get("role")) for n in actor_nodes}

    fallback = _fallback_positions(actor_ids, actor_roles)
    actor_info: dict[str, ActorInfo] = {}

    for node in actor_nodes:
        actor_id = node["id"]
        role = actor_roles[actor_id]
        description = str(node.get("description") or node.get("label") or actor_id)

        lat = None
        lon = None
        for key in _canonical_coord_keys(actor_id, role):
            if key in coords:
                coord = coords[key]
                if isinstance(coord, list) and len(coord) >= 2:
                    lat = _safe_float(coord[0], default=float("nan"))
                    lon = _safe_float(coord[1], default=float("nan"))
                    break

        if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
            fx, fy = fallback[actor_id]
            lon = fx
            lat = fy

        actor_info[actor_id] = ActorInfo(
            actor_id=actor_id,
            role=role,
            description=description,
            lat=float(lat),
            lon=float(lon),
        )
    return actor_info


def _zone_scores_from_report(report: dict) -> dict[str, float]:
    bottlenecks = report.get("des_distribution", {}).get("top_bottlenecks", [])
    raw_scores: dict[str, float] = {
        "supplier_to_manufacturer": 0.0,
        "manufacturing_internal": 0.0,
        "manufacturer_to_distribution": 0.0,
        "distribution_to_customer": 0.0,
        "other": 0.0,
    }

    for item in bottlenecks:
        key = str(item.get("link_backlog_key", ""))
        p95 = float(item.get("p95_max_backlog", 0.0))
        zone = _stage_zone_from_backlog_key(key)
        raw_scores[zone] = max(raw_scores.get(zone, 0.0), p95)

    max_score = max(raw_scores.values()) if raw_scores else 0.0
    if max_score <= 1e-12:
        return {k: 0.0 for k in raw_scores}
    return {k: v / max_score for k, v in raw_scores.items()}


def _sd_reception_score(report: dict) -> dict[str, float]:
    summary = report.get("sd_frequency", {}).get("summary", {})
    stock_summary = summary.get("stock_arrivee", {})
    backlog_summary = summary.get("backlog_client", {})
    gain_db = float(stock_summary.get("peak_gain_db", 0.0))
    distortion = float(stock_summary.get("max_distortion_ratio", 0.0))
    backlog_gain = float(backlog_summary.get("peak_gain_db", -300.0))

    gain_score = min(1.0, max(0.0, gain_db / 24.0))
    distortion_score = min(1.0, max(0.0, distortion / 0.35))
    backlog_score = min(1.0, max(0.0, (backlog_gain + 12.0) / 12.0))
    score = max(gain_score, 0.65 * distortion_score, 0.45 * backlog_score)

    return {
        "score": score,
        "stock_peak_gain_db": gain_db,
        "stock_distortion_ratio": distortion,
        "backlog_peak_gain_db": backlog_gain,
    }


def _build_supply_edges(
    graph: dict,
    actor_info: dict[str, ActorInfo],
    zone_scores: dict[str, float],
    data_poc: DataPocInfo | None = None,
) -> list[SupplyEdgeInfo]:
    raw_edges: list[dict] = []
    product_suppliers: dict[str, set[str]] = defaultdict(set)
    target_in_degree: Counter[str] = Counter()
    distances_km: list[float] = []
    unit_costs: list[float] = []

    for edge in graph.get("edges", []):
        if edge.get("relation") != "SUPPLIES":
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source not in actor_info or target not in actor_info:
            continue
        raw_edges.append(edge)
        product = _normalize_product(str(edge.get("product") or ""))
        product_suppliers[product].add(source)
        target_in_degree[target] += 1

        src = actor_info[source]
        dst = actor_info[target]
        stored_km = _stored_route_km(source, target)
        if stored_km is not None:
            distances_km.append(stored_km)

        if data_poc is not None:
            source_keys = _actor_sheet_keys(source, actor_info[source].role)
            target_keys = _actor_sheet_keys(target, actor_info[target].role)
            relation_data = None
            for sk in source_keys:
                for tk in target_keys:
                    candidate = data_poc.relation_by_triplet.get((sk, tk, product))
                    if candidate is not None:
                        relation_data = candidate
                        break
                if relation_data is not None:
                    break
            if relation_data is not None:
                sell_price = relation_data.get("sell_price")
                price_base = relation_data.get("price_base")
            else:
                sell_price = edge.get("sell_price")
                price_base = edge.get("price_base")
        else:
            sell_price = edge.get("sell_price")
            price_base = edge.get("price_base")

        if isinstance(sell_price, (int, float)) and isinstance(price_base, (int, float)) and price_base not in (0, 0.0):
            if not (math.isnan(float(sell_price)) or math.isnan(float(price_base))):
                unit_costs.append(max(0.0, float(sell_price) / float(price_base)))

    if not raw_edges:
        return []

    scarcity_values = [1.0 / max(1, len(product_suppliers[_normalize_product(str(e.get("product") or ""))])) for e in raw_edges]
    max_in_degree = max(target_in_degree.values()) if target_in_degree else 1
    min_dist = min(distances_km) if distances_km else 0.0
    max_dist = max(distances_km) if distances_km else 1.0
    min_scarcity = min(scarcity_values) if scarcity_values else 0.0
    max_scarcity = max(scarcity_values) if scarcity_values else 1.0
    min_cost = min(unit_costs) if unit_costs else 0.0
    max_cost = max(unit_costs) if unit_costs else 1.0

    def _norm(value: float, vmin: float, vmax: float) -> float:
        if vmax - vmin <= 1e-12:
            return 0.5
        return min(1.0, max(0.0, (value - vmin) / (vmax - vmin)))

    out: list[SupplyEdgeInfo] = []
    raw_scores: list[float] = []
    for edge in raw_edges:
        source = edge["source"]
        target = edge["target"]

        source_role = actor_info[source].role
        target_role = actor_info[target].role
        zone = _role_flow_zone(source_role, target_role)
        zone_risk = zone_scores.get(zone, 0.0)
        if zone == "other":
            zone_risk = max(zone_risk, zone_scores.get("manufacturing_internal", 0.0) * 0.7)

        product = _normalize_product(str(edge.get("product") or ""))
        supplier_count = max(1, len(product_suppliers[product]))
        scarcity = _norm(1.0 / supplier_count, min_scarcity, max_scarcity)
        concentration = min(1.0, max(0.0, target_in_degree[target] / max_in_degree))

        src = actor_info[source]
        dst = actor_info[target]
        distance = _stored_route_km(source, target)
        distance_norm = _norm(distance, min_dist, max_dist) if distance is not None else 0.5

        relation_data = None
        if data_poc is not None:
            source_keys = _actor_sheet_keys(source, actor_info[source].role)
            target_keys = _actor_sheet_keys(target, actor_info[target].role)
            for sk in source_keys:
                for tk in target_keys:
                    candidate = data_poc.relation_by_triplet.get((sk, tk, product))
                    if candidate is not None:
                        relation_data = candidate
                        break
                if relation_data is not None:
                    break

        if relation_data is not None:
            sell_price = relation_data.get("sell_price")
            price_base = relation_data.get("price_base")
        else:
            sell_price = edge.get("sell_price")
            price_base = edge.get("price_base")

        if isinstance(sell_price, (int, float)) and isinstance(price_base, (int, float)) and price_base not in (0, 0.0):
            if not (math.isnan(float(sell_price)) or math.isnan(float(price_base))):
                unit_cost = max(0.0, float(sell_price) / float(price_base))
                cost_norm = _norm(unit_cost, min_cost, max_cost)
            else:
                cost_norm = 0.5
        else:
            cost_norm = 0.5

        bom_criticality = 0.5
        if data_poc is not None and data_poc.product_bom_criticality:
            if product in data_poc.product_bom_criticality:
                bom_criticality = data_poc.product_bom_criticality[product]
            elif zone in ("manufacturer_to_distribution", "distribution_to_customer"):
                bom_criticality = 0.85
            else:
                bom_criticality = 0.2

        risk = (
            0.34 * zone_risk
            + 0.22 * scarcity
            + 0.16 * concentration
            + 0.10 * distance_norm
            + 0.08 * cost_norm
            + 0.10 * bom_criticality
        )
        raw_scores.append(risk)

        out.append(
            SupplyEdgeInfo(
                source=source,
                target=target,
                product=product,
                relation=str(edge.get("relation", "")),
                zone=zone,
                risk_score=float(risk),
                risk_display=0.0,
                material_family=_material_family(actor_info[source].description),
            )
        )
        if data_poc is not None:
            if relation_data is not None:
                data_poc.matched_relations += 1

    if len(out) == 1:
        out[0].risk_display = 1.0
    else:
        ranked = sorted(enumerate(raw_scores), key=lambda x: x[1])
        for rank, (idx, _) in enumerate(ranked):
            out[idx].risk_display = rank / float(len(out) - 1)
    return out


def _short_actor_label(actor_id: str) -> str:
    code = _extract_code(actor_id)
    if code:
        return code
    return actor_id.replace("Actor:", "")


def _role_color(role: str) -> str:
    return {
        "Supplier Distribution Center": "#4C78A8",
        "Manufacturer": "#F58518",
        "Distribution Center": "#54A24B",
        "Customer": "#E45756",
    }.get(role, "#9D9DA3")


def _zone_color(zone: str) -> str:
    return {
        "supplier_to_manufacturer": "#1F77B4",
        "manufacturing_internal": "#D62728",
        "manufacturer_to_distribution": "#FF7F0E",
        "distribution_to_customer": "#2CA02C",
        "other": "#7F7F7F",
    }.get(zone, "#7F7F7F")


def _top_edge_rows(edges: list[SupplyEdgeInfo], limit: int = 14) -> list[str]:
    ordered = sorted(
        edges,
        key=lambda e: (e.risk_score, e.zone, e.material_family, e.product, e.source, e.target),
        reverse=True,
    )
    rows: list[str] = []
    for edge in ordered[:limit]:
        s = _short_actor_label(edge.source)
        t = _short_actor_label(edge.target)
        rows.append(
            f"{s} -> {t} | product={edge.product} | type={edge.material_family} | zone={edge.zone} | risk={edge.risk_score:.2f} | display={edge.risk_display:.2f}"
        )
    return rows


def _detailed_text_report(
    report: dict,
    edges: list[SupplyEdgeInfo],
    zone_scores: dict[str, float],
    sd_reception: dict[str, float],
    data_poc: DataPocInfo | None = None,
) -> str:
    lines = []
    lines.append("Supply issue localization report")
    lines.append("")
    lines.append("DES zone risk scores (normalized):")
    lines.append(f"- supplier_to_manufacturer: {zone_scores.get('supplier_to_manufacturer', 0.0):.3f}")
    lines.append(f"- manufacturing_internal: {zone_scores.get('manufacturing_internal', 0.0):.3f}")
    lines.append(f"- manufacturer_to_distribution: {zone_scores.get('manufacturer_to_distribution', 0.0):.3f}")
    lines.append(f"- distribution_to_customer: {zone_scores.get('distribution_to_customer', 0.0):.3f}")
    lines.append("")
    lines.append("SD reception-node indicators:")
    lines.append(f"- reception_score_0_1: {sd_reception.get('score', 0.0):.3f}")
    lines.append(f"- stock_peak_gain_db: {sd_reception.get('stock_peak_gain_db', 0.0):.3f}")
    lines.append(f"- stock_distortion_ratio: {sd_reception.get('stock_distortion_ratio', 0.0):.3f}")
    lines.append(f"- backlog_peak_gain_db: {sd_reception.get('backlog_peak_gain_db', 0.0):.3f}")
    if data_poc is not None:
        lines.append("")
        lines.append("Data_poc enrichment:")
        lines.append(f"- relation_rows_loaded: {len(data_poc.relation_by_triplet)}")
        lines.append(f"- relation_rows_matched_to_graph_edges: {data_poc.matched_relations}")
        lines.append(f"- bom_products_with_criticality: {len(data_poc.product_bom_criticality)}")
    lines.append("")
    lines.append("Top localized risky links:")
    lines.extend([f"- {row}" for row in _top_edge_rows(edges)])

    issues = report.get("issues", [])
    if issues:
        lines.append("")
        lines.append("Detected issues:")
        for issue in issues:
            sev = issue.get("severity", "n/a")
            area = issue.get("area", "n/a")
            text = issue.get("issue", "")
            lines.append(f"- [{sev}] {area}: {text}")

    return "\n".join(lines)


def plot_annotated_supply_graph(
    graph_path: str | Path,
    coords_path: str | Path,
    report_path: str | Path,
    output_path: str | Path,
    output_json: str | Path | None = None,
    output_text: str | Path | None = None,
    data_poc_path: str | Path | None = "Data_poc.xlsx",
) -> dict[str, object]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    coords = json.loads(Path(coords_path).read_text(encoding="utf-8"))
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    data_poc = _load_data_poc(data_poc_path)

    actor_info = _build_actor_info(graph, coords)
    zone_scores = _zone_scores_from_report(report)
    sd_reception = _sd_reception_score(report)
    edges = _build_supply_edges(graph, actor_info, zone_scores, data_poc=data_poc)

    fig, ax_graph = plt.subplots(1, 1, figsize=(14, 9))

    edge_cmap = plt.colormaps["turbo"]
    for edge in edges:
        src = actor_info[edge.source]
        dst = actor_info[edge.target]
        display_score = min(1.0, max(0.0, edge.risk_display))
        color = edge_cmap(display_score)
        width = 0.6 + 4.2 * display_score
        alpha = 0.10 + 0.80 * display_score
        ax_graph.plot([src.lon, dst.lon], [src.lat, dst.lat], color=color, linewidth=width, alpha=alpha, zorder=1)

    roles = sorted({a.role for a in actor_info.values()})
    for role in roles:
        role_nodes = [a for a in actor_info.values() if a.role == role]
        xs = [a.lon for a in role_nodes]
        ys = [a.lat for a in role_nodes]
        ax_graph.scatter(
            xs,
            ys,
            s=70,
            color=_role_color(role),
            edgecolor="black",
            linewidth=0.5,
            alpha=0.9,
            label=role,
            zorder=2,
        )

    reception_nodes = [a for a in actor_info.values() if a.role == "Customer"]
    if reception_nodes:
        rx = [a.lon for a in reception_nodes]
        ry = [a.lat for a in reception_nodes]
        r_score = min(1.0, max(0.0, sd_reception.get("score", 0.0)))
        halo_color = plt.cm.Blues(0.35 + 0.65 * r_score)
        ax_graph.scatter(
            rx,
            ry,
            s=550,
            facecolors="none",
            edgecolors=halo_color,
            linewidths=2.8 + 2.2 * r_score,
            alpha=0.95,
            zorder=3,
        )

    for actor in actor_info.values():
        ax_graph.text(
            actor.lon,
            actor.lat,
            _short_actor_label(actor.actor_id),
            fontsize=8,
            ha="left",
            va="bottom",
            color="#202020",
            zorder=3,
        )

    sm = plt.cm.ScalarMappable(cmap=edge_cmap, norm=plt.Normalize(vmin=0.0, vmax=1.0))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax_graph, fraction=0.03, pad=0.02)
    cbar.set_label("DES link risk percentile rank (0-1)")

    sd_label = (
        "SD reception stress: "
        f"{sd_reception.get('score', 0.0):.2f} "
        f"(gain={sd_reception.get('stock_peak_gain_db', 0.0):.1f} dB)"
    )
    proxy = Line2D([0], [0], marker="o", markersize=10, color="none", markerfacecolor="none", markeredgecolor="#1f4e79", lw=0)
    handles, labels = ax_graph.get_legend_handles_labels()
    handles.append(proxy)
    labels.append(sd_label)

    ax_graph.set_title("Supply knowledge graph - risk links and SD reception marker")
    ax_graph.set_xlabel("Longitude / fallback x")
    ax_graph.set_ylabel("Latitude / fallback y")
    ax_graph.grid(alpha=0.2)
    ax_graph.legend(handles=handles, labels=labels, loc="upper left", fontsize=8, framealpha=0.9)

    fig.suptitle("Supply chain graph annotations (visual only)", y=0.99)
    plt.tight_layout()
    ax_graph.clear()
    ax_graph.set_axis_off()
    ax_graph.text(0.5,0.5,'Positions des sites retirées de la version publique',ha='center',transform=ax_graph.transAxes)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)

    detailed_text = _detailed_text_report(report, edges, zone_scores, sd_reception, data_poc=data_poc)

    payload = {
        "graph_path": str(graph_path),
        "coords_path": str(coords_path),
        "report_path": str(report_path),
        "output_png": str(output_path),
        "zone_scores": zone_scores,
        "sd_reception": sd_reception,
        "data_poc_used": data_poc is not None,
        "data_poc_relation_rows": 0 if data_poc is None else len(data_poc.relation_by_triplet),
        "data_poc_relation_rows_matched": 0 if data_poc is None else data_poc.matched_relations,
        "data_poc_bom_criticality_products": 0 if data_poc is None else len(data_poc.product_bom_criticality),
        "top_localized_links": _top_edge_rows(edges),
        "detailed_report": detailed_text,
    }

    if output_json is not None:
        Path(output_json).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    if output_text is not None:
        Path(output_text).write_text(detailed_text, encoding="utf-8")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot knowledge graph and annotate localized supply issues")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json", help="Path to knowledge_graph.json")
    parser.add_argument("--coords", type=str, default="actor_coords.json", help="Path to actor_coords.json")
    parser.add_argument(
        "--report",
        type=str,
        default="advanced_complex_full_report.json",
        help="Path to advanced diagnostics report JSON",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="supply_issue_annotated.png",
        help="Output PNG path",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="supply_issue_annotated.json",
        help="Output JSON metadata",
    )
    parser.add_argument(
        "--out-text",
        type=str,
        default="supply_issue_annotated_report.txt",
        help="Output full text report",
    )
    parser.add_argument(
        "--data-poc",
        type=str,
        default="Data_poc.xlsx",
        help="Optional Data_poc.xlsx path for enrichment",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = plot_annotated_supply_graph(
        graph_path=args.graph,
        coords_path=args.coords,
        report_path=args.report,
        output_path=args.out,
        output_json=args.out_json,
        output_text=args.out_text,
        data_poc_path=args.data_poc,
    )
    print(f"Annotated graph PNG: {payload['output_png']}")
    print(f"Zone scores: {payload['zone_scores']}")
    print(f"SD reception score: {payload['sd_reception']['score']:.3f}")
    print(f"Top links listed: {len(payload['top_localized_links'])}")


if __name__ == "__main__":
    main()
